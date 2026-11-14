"""Produit une édition.

Usage : `python -m veille.edition [--type matin|soir|weekend] [--heures N] [--a-blanc]`.

Sans option : lit l'état sur `data`, écrit `editions/AAAA-MM-JJ-<type>.json` et envoie le message
Telegram. --heures N : fenêtre forcée aux N dernières heures (premier essai, reprise).
--a-blanc : état local `_etat_local/`, aucun envoi Telegram.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import timedelta

from veille import temps
from veille.config import charger_parametres
from veille.edition import message
from veille.edition.fenetre import (
    CHEMIN_HISTORIQUE,
    calculer_fenetre,
    charger_articles,
    fichier_et_id,
    type_depuis_cron,
    type_pour,
)
from veille.edition.generation import AucuneActualite, produire_edition
from veille.edition.modele import EditionInvalide
from veille.etat import EtatGit, EtatLocal
from veille.http import Client
from veille.ia import ErreurIa, Ia
from veille.journal import Journal
from veille.marches import mizeniti, tableaux, yahoo
from veille.telegram import envoyer

NOMS = {"matin": "du matin", "soir": "du soir", "weekend": "du week-end"}


def url_pages() -> str | None:
    depot = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" not in depot:
        return None
    proprietaire, nom = depot.split("/", 1)
    return f"https://{proprietaire.lower()}.github.io/{nom}/"


def donnees_marches(client, params: dict, journal: Journal) -> dict | None:
    """Chiffres et tableaux des chapitres 3 et 4 ; une panne ne bloque jamais l'édition."""
    try:
        bourse, taux = mizeniti.charger(client, params["marches"]["mizeniti_url"], journal)
        internationaux = yahoo.lire_internationaux(client, journal)
        return {
            "chiffres": tableaux.chiffres(bourse, internationaux, taux),
            "tableaux": {
                "bourse-entreprises": tableaux.tableau_bourse(bourse),
                "international": tableaux.tableau_international(internationaux, taux),
            },
        }
    except Exception as exc:  # noqa: BLE001 - édition sans tableaux plutôt que pas d'édition
        journal.avertir("marches_indisponibles", journal.masquer(str(exc))[:160])
        return None


def option(argv: list[str], nom: str) -> str | None:
    return argv[argv.index(nom) + 1] if nom in argv and argv.index(nom) + 1 < len(argv) else None


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):  # absent sous la capture de pytest
        sys.stdout.reconfigure(encoding="utf-8")
    a_blanc = "--a-blanc" in argv
    journal = Journal.depuis_env()
    params = charger_parametres()
    client = Client(journal=journal, essais=params["http"]["essais"])
    etat = (
        EtatLocal("_etat_local")
        if a_blanc
        else EtatGit.depuis_environnement(journal=journal).ouvrir()
    )
    token = None if a_blanc else os.environ.get("TG_TOKEN_VEILLE")
    chat_id = None if a_blanc else os.environ.get("TG_CHAT_ID")

    def telegram(type_message: str, corps: str) -> bool:
        if not (token and chat_id):
            return False
        try:
            envoyer(
                type_message, corps, token=token, chat_id=chat_id, client=client, journal=journal
            )
            return True
        except Exception as exc:  # noqa: BLE001 - l'édition est déjà enregistrée, on journalise
            journal.erreur("edition_telegram_echec", journal.masquer(str(exc))[:200])
            return False

    maintenant = temps.maintenant()
    demande = option(argv, "--type") or "auto"
    type_edition = (
        demande
        if demande != "auto"
        else type_depuis_cron(os.environ.get("EDITION_SCHEDULE", "")) or type_pour(maintenant)
    )
    ident, enregistre = fichier_et_id(type_edition, maintenant)
    historique = etat.lire_json(CHEMIN_HISTORIQUE, [])
    if option(argv, "--heures"):
        debut, fin = maintenant - timedelta(hours=float(option(argv, "--heures"))), maintenant
    else:
        debut, fin = calculer_fenetre(type_edition, maintenant, historique)
    articles = charger_articles(etat, debut, fin)
    print(f"Édition {ident} ({type_edition}) : fenêtre {debut.isoformat()} → {fin.isoformat()}, "
          f"{len(articles)} article(s)")  # fmt: skip

    ia = Ia.depuis_environnement(params, client, journal, etat=etat)
    try:
        edition = produire_edition(
            ia=ia, articles=articles, type_enregistre=enregistre, ident=ident,
            maintenant=maintenant, journal=journal,
            marches=donnees_marches(client, params, journal),
        )  # fmt: skip
    except AucuneActualite as exc:
        journal.avertir("edition_vide", str(exc), edition=ident)
        telegram(enregistre, f"Aucune actualité retenue pour la synthèse {NOMS[type_edition]}.")
        print("Aucune actualité retenue :", exc)
        return 0
    except (ErreurIa, EditionInvalide) as exc:
        raison = journal.masquer(str(exc))[:300]
        journal.erreur("edition_non_generee", raison, edition=ident)
        telegram("sante", f"Synthèse {NOMS[type_edition]} non générée : {message_echapper(raison)}")
        print("ÉCHEC :", raison)
        _journal(etat, journal, a_blanc)
        return 1

    contenu = json.dumps(edition, ensure_ascii=False, indent=1) + "\n"

    def ecrire(tx) -> None:
        tx.ecrire(f"editions/{ident}.json", contenu)
        entrees = [
            h for h in json.loads(tx.lire(CHEMIN_HISTORIQUE, "[]") or "[]") if h["id"] != ident
        ]
        entrees.append({"id": ident, "debut": debut.isoformat(), "fin": fin.isoformat()})
        tx.ecrire(CHEMIN_HISTORIQUE, json.dumps(entrees[-60:], ensure_ascii=False) + "\n")

    etat.transaction(f"data: édition {ident}", ecrire)
    base = url_pages()
    texte = message.construire_message(edition, f"{base}editions/{ident}.html" if base else None)
    envoye = telegram(enregistre, texte)
    nb = sum(len(c["sujets"]) for c in edition["chapitres"])
    etat_telegram = "envoyé" if envoye else "non envoyé"
    print(
        f"Édition {ident} écrite : {nb} sujet(s), {len(edition['articles'])} article(s), "
        f"modèle {edition['modele']}, Telegram : {etat_telegram}"
    )
    _journal(etat, journal, a_blanc)
    return 0


def message_echapper(texte: str) -> str:
    from veille.telegram import echapper

    return echapper(texte)


def _journal(etat, journal: Journal, a_blanc: bool) -> None:
    if a_blanc:
        return
    utiles = [
        e for e in journal.evenements
        if e["niveau"] != "info" or e["code"] == "edition_produite"
    ]  # fmt: skip
    if utiles:
        lignes = [json.dumps(e, ensure_ascii=False) for e in utiles]
        etat.ajouter_lignes(f"sante/{temps.mois()}.jsonl", lignes, "data: journal d'édition")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
