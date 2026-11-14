"""Point d'entrée : `python -m veille.collecte [--a-blanc]`.

Sans option : état sur la branche `data`, alertes sur Telegram (workflow `collecte`).
--a-blanc : état dans `_etat_local/`, aucun envoi Telegram (essai local sur de vraies pages).
"""

from __future__ import annotations

import json
import os
import sys

from veille import temps
from veille.collecte.filtre import Filtre
from veille.collecte.orchestrateur import collecter
from veille.config import charger_parametres, charger_regles_filtre, charger_sources
from veille.etat import EtatGit, EtatLocal
from veille.http import Client
from veille.journal import Journal


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # console Windows : cp1252 par défaut
    a_blanc = "--a-blanc" in argv
    journal = Journal.depuis_env()
    params = charger_parametres()
    client = Client(
        journal=journal,
        essais=params["http"]["essais"],
        delai_hote=params["http"]["delai_hote_s"],
    )
    etat = (
        EtatLocal("_etat_local")
        if a_blanc
        else EtatGit.depuis_environnement(journal=journal).ouvrir()
    )
    sources = [s for s in charger_sources() if s["actif"]]
    token = None if a_blanc else os.environ.get("TG_TOKEN_VEILLE")
    chat_id = None if a_blanc else os.environ.get("TG_CHAT_ID")
    if not a_blanc and not (token and chat_id):
        journal.erreur("telegram_non_configure", "TG_TOKEN_VEILLE ou TG_CHAT_ID absent")

    rapport = collecter(
        sources=sources,
        client=client,
        journal=journal,
        etat=etat,
        filtre=Filtre(charger_regles_filtre()),
        maintenant=temps.maintenant(),
        token=token,
        chat_id=chat_id,
    )

    r = rapport
    print(f"\n=== Collecte : {r.sources_ok}/{len(sources)} sources lues, {r.lus} articles")
    print(f"    nouveaux : {r.nouveaux} | rejetés par le filtre : {r.rejetes}")
    print(f"    liens Google News résolus : {r.resolutions} (échecs : {r.resolutions_echec})")
    print(f"    alertes envoyées : {r.alertes_envoyees} | en attente : {r.alertes_en_attente}")
    for sid, message in sorted(r.sources_en_erreur.items()):
        print(f"    ⚠ {sid} : {message}")

    if not a_blanc:
        # journal de santé : seulement ce qui mérite d'être relu (pas le bruit « info »)
        utiles = [
            e
            for e in journal.evenements
            if e["niveau"] != "info" or e["code"] == "collecte_terminee"
        ]
        lignes = [json.dumps(e, ensure_ascii=False) for e in utiles]
        etat.ajouter_lignes(f"sante/{temps.mois()}.jsonl", lignes, "data: journal de collecte")
    return 1 if rapport.sources_ok == 0 else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
