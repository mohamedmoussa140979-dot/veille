"""Envoi d'une édition validée vers Mizeniti (contrat AC3 paragraphe 4, spec § 8.4).

`POST <mizeniti.actualites_url>/actualites/ingest`, `Authorization: Bearer $MIZENITI_INGEST_TOKEN`,
corps = le fichier `edition.v1.json` tel qu'écrit sur la branche `data`.

Règles :
- sans jeton, l'envoi est sauté (une ligne au journal) ;
- un échec (réseau, 4xx, 5xx) n'empêche rien d'autre : ni Telegram, ni l'archive Pages, ni le code
  de sortie de l'édition. Il est journalisé en `ingest_echec` (niveau erreur), que le contrôle de
  santé relit à 21:00 ;
- ni le corps ni le jeton ne sont jamais journalisés : seuls un code HTTP ou une cause générique.
"""

from __future__ import annotations

import os

from veille.http import ErreurReseau
from veille.journal import Journal

DELAI_S = 20.0
ESSAIS = 3  # spec § 8.4 : trois essais (5xx, 429 et réseau ; un 4xx n'est pas réessayé)


def envoyer_edition(client, params: dict, edition_json: str, ident: str, journal: Journal) -> str:
    """Retourne « envoye », « saute » ou « echec » ; ne lève jamais."""
    token = os.environ.get("MIZENITI_INGEST_TOKEN") or None
    if not token:
        journal.info("ingest_saute", f"édition {ident} : MIZENITI_INGEST_TOKEN absent, envoi sauté")
        return "saute"
    base = (params.get("mizeniti") or {}).get("actualites_url")
    if not base:
        journal.erreur(
            "ingest_echec",
            f"édition {ident} non envoyée : mizeniti.actualites_url absent des paramètres",
            raison="adresse du Worker absente",
            edition=ident,
        )
        return "echec"
    raison = None
    try:
        reponse = client.post(
            base.rstrip("/") + "/actualites/ingest",
            data=edition_json.encode("utf-8"),
            timeout=DELAI_S,
            essais=ESSAIS,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
                "User-Agent": "veille-actions",
            },
        )
        if not 200 <= reponse.status_code < 300:
            raison = f"HTTP {reponse.status_code}"
    except ErreurReseau:
        raison = "serveur injoignable (réseau ou délai)"
    except Exception as exc:  # noqa: BLE001 - l'envoi ne doit jamais faire échouer l'édition
        raison = f"erreur inattendue ({type(exc).__name__})"
    if raison:
        journal.erreur(
            "ingest_echec",
            f"édition {ident} non envoyée à Mizeniti : {journal.masquer(raison)}",
            raison=raison,
            edition=ident,
        )
        return "echec"
    journal.info("ingest_ok", f"édition {ident} envoyée à Mizeniti", edition=ident)
    return "envoye"
