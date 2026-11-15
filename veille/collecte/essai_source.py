"""Mode test d'une source (contrat AC3, paragraphes 3 et 4) : bouton « Tester » du back-office.

Ne lit QUE la source demandée, n'envoie aucune alerte, n'ouvre pas la branche `data` (donc ne
modifie aucun état), puis renvoie le résultat au Worker :

    POST <mizeniti.actualites_url>/veille/resultat-test
    Authorization: Bearer $VEILLE_CONFIG_TOKEN
    {"demande_id", "source_id", "ok", "articles": [{"titre", "url", "publie_le"}], "erreur"}

Plafonds du contrat : 30 articles au plus, titres tronqués à 200 caractères, jamais de texte
d'article (seuls titre, lien et date partent). Source inconnue ou inactive : `ok: false` avec une
erreur lisible. Les liens Google News ne sont pas résolus ici (l'essai reste léger).
"""

from __future__ import annotations

import os
import re

from veille import temps
from veille.collecte.article import nettoyer_url
from veille.collecte.orchestrateur import Rapport, _recolter
from veille.config_distante import Configuration
from veille.http import ErreurReseau
from veille.journal import Journal

MAX_ARTICLES = 30
TITRE_MAX = 200
ERREUR_MAX = 300
ID_SOURCE = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
ID_DEMANDE = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")


def _erreur(source_id: str, message: str) -> dict:
    return {
        "source_id": source_id[:80],
        "ok": False,
        "articles": [],
        "erreur": message[:ERREUR_MAX],
    }


def executer(source_id: str, config: Configuration, client, journal: Journal) -> dict:
    """Corps du résultat (sans `demande_id`). Ne lève jamais."""
    if not ID_SOURCE.match(source_id or ""):
        return _erreur(source_id or "", "Identifiant de source invalide.")
    complement = ""
    if config.origine == "locale" and config.raison_repli:
        complement = f" (configuration locale utilisée : {config.raison_repli})"
    if source_id in config.ignorees:
        return _erreur(
            source_id, "Source ignorée : son type n'est pas pris en charge par la veille."
        )
    source = next((s for s in config.sources if s["id"] == source_id), None)
    if source is None:
        return _erreur(source_id, f"Source inconnue de la veille{complement}.")
    if not source["actif"]:
        return _erreur(
            source_id, "Source inactive : l'activer dans le back-office avant de la tester."
        )

    rapport = Rapport()
    articles = _recolter([source], client, journal, temps.maintenant(), {}, rapport)
    if not articles:
        raison = rapport.sources_en_erreur.get(source_id, "aucun article lu")
        return _erreur(source_id, f"La lecture a échoué : {raison}")
    return {
        "source_id": source_id,
        "ok": True,
        "articles": [
            {
                "titre": a.titre[:TITRE_MAX],
                "url": nettoyer_url(a.url),
                "publie_le": a.publie_le or None,
            }
            for a in articles[:MAX_ARTICLES]
        ],
        "erreur": None,
    }


def envoyer_resultat(client, params: dict, corps: dict, journal: Journal) -> bool:
    """POST du résultat au Worker ; sans jeton ou en cas d'échec : journalisé, retourne False."""
    token = os.environ.get("VEILLE_CONFIG_TOKEN") or None
    base = (params.get("mizeniti") or {}).get("actualites_url")
    if not token or not base:
        journal.erreur(
            "test_source_non_envoye",
            "résultat non envoyé : VEILLE_CONFIG_TOKEN ou mizeniti.actualites_url absent",
            raison="jeton ou adresse absent",
        )
        return False
    raison = None
    try:
        reponse = client.post(
            base.rstrip("/") + "/veille/resultat-test",
            json=corps,
            timeout=20.0,
            essais=3,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "User-Agent": "veille-actions",
            },
        )
        if not 200 <= reponse.status_code < 300:
            raison = f"HTTP {reponse.status_code}"
    except ErreurReseau:
        raison = "serveur injoignable (réseau ou délai)"
    except Exception as exc:  # noqa: BLE001
        raison = f"erreur inattendue ({type(exc).__name__})"
    if raison:
        journal.erreur(
            "test_source_non_envoye",
            f"résultat non envoyé : {journal.masquer(raison)}",
            raison=raison,
        )
        return False
    return True


def lancer(source_id: str, demande_id: str | None, config, client, journal, params: dict) -> int:
    """Point d'entrée du mode test. Code 0 si le résultat est parti (ou essai local sans
    demande) ; 1 si une demande réelle n'a pas pu être rendue au Worker."""
    resultat = executer(source_id, config, client, journal)
    etat = "OK" if resultat["ok"] else f"ÉCHEC : {resultat['erreur']}"
    nb = len(resultat["articles"])
    print(f"Test de la source {resultat['source_id']} : {etat} ({nb} article(s))")
    if not demande_id:
        print("Pas de demande_id : essai local, rien n'est envoyé.")
        return 0
    if not ID_DEMANDE.match(demande_id):
        print("demande_id invalide : résultat non envoyé.")
        return 1
    corps = {"demande_id": demande_id, **resultat}
    envoye = envoyer_resultat(client, params, corps, journal)
    print("Résultat envoyé au Worker." if envoye else "Résultat NON envoyé (voir le journal).")
    return 0 if envoye else 1
