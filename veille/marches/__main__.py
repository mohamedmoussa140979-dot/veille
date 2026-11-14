"""Points 📈 : `python -m veille.marches --point bourse|international [--essai 1|2] [--jour J]`.

- bourse : séance du jour, publiée par Mizeniti. 17:20 (essai 1) : rien si la séance n'est pas
  encore publiée ; 18:20 (essai 2) : message « séance du JJ/MM non encore publiée ». Jours sans
  séance (week-end, jours fériés de `config/jours_feries.yaml`) : aucun message.
- international : clôture internationale (Yahoo) et taux BCT, 22:45.
"""

from __future__ import annotations

import json
import os
import sys

import yaml

from veille import temps
from veille.config import RACINE, charger_parametres
from veille.etat import EtatGit, EtatLocal
from veille.http import Client
from veille.journal import Journal
from veille.marches import mizeniti, points, tableaux, yahoo
from veille.telegram import envoyer

# Horaire du workflow (UTC) -> (point, essai) : fiable même si GitHub retarde l'exécution.
CRONS = {
    "20 16 * * 1-5": ("bourse", 1),  # 17:20 à Tunis
    "20 17 * * 1-5": ("bourse", 2),  # 18:20
    "45 21 * * 1-5": ("international", 1),  # 22:45
}
CHEMIN_ETAT = "state/marches.json"


def jours_feries() -> set[str]:
    fichier = RACINE / "config" / "jours_feries.yaml"
    donnees = yaml.safe_load(fichier.read_text(encoding="utf-8")) or {}
    return {str(j) for j in donnees.get("jours_feries", [])}


def option(argv: list[str], nom: str) -> str | None:
    return argv[argv.index(nom) + 1] if nom in argv and argv.index(nom) + 1 < len(argv) else None


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
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

    point, essai = option(argv, "--point"), int(option(argv, "--essai") or 1)
    if not point:
        point, essai = CRONS.get(os.environ.get("MARCHES_SCHEDULE", "").strip(), (None, 1))
    if point not in ("bourse", "international"):
        print("usage : python -m veille.marches --point bourse|international [--essai 1|2]")
        return 2

    maintenant = temps.maintenant()
    essai_manuel = option(argv, "--jour")  # essai : jour imposé, sans garde-fou ni mémorisation
    jour = essai_manuel or temps.en_tunis(maintenant).date().isoformat()
    sans_seance = temps.en_tunis(maintenant).weekday() >= 5 or jour in jours_feries()
    if sans_seance and not essai_manuel:
        print(f"{jour} : jour sans séance, aucun point.")
        return 0

    base = params["marches"]["mizeniti_url"]
    etat_marches = etat.lire_json(CHEMIN_ETAT, {})
    if point == "bourse":
        if etat_marches.get("bourse_envoye") == jour and not essai_manuel:
            print("Point Bourse déjà envoyé aujourd'hui.")
            return 0
        bourse, _taux = mizeniti.charger(client, base, journal)
        publiee = bourse is not None and bourse["seance"] == jour
        if not publiee and essai == 1:
            journal.info("bourse_non_publiee", f"séance du {jour} pas encore publiée")
            print("Séance du jour non encore publiée : nouvel essai à 18:20.")
            return 0
        corps = points.message_bourse(bourse, jour)
    else:
        _bourse, taux = mizeniti.charger(client, base, journal)
        internationaux = yahoo.lire_internationaux(client, journal)
        tableau = tableaux.tableau_international(internationaux, taux)
        corps = points.message_international(tableau, taux)

    print(corps.replace("<b>", "").replace("</b>", ""))
    code, envoye = 0, False
    if token and chat_id:
        try:
            envoyer("marches", corps, token=token, chat_id=chat_id, client=client, journal=journal)
            envoye = True
        except Exception as exc:  # noqa: BLE001 - journalisé, code de sortie non nul
            journal.erreur("marches_telegram_echec", journal.masquer(str(exc))[:200], point=point)
            code = 1
    if envoye and point == "bourse" and not essai_manuel:
        etat.modifier_json(
            CHEMIN_ETAT,
            lambda d: {**d, "bourse_envoye": jour},
            defaut={},
            message="data: point Bourse",
        )
    if not a_blanc:
        utiles = [e for e in journal.evenements if e["niveau"] != "info"]
        if utiles:
            etat.ajouter_lignes(
                f"sante/{temps.mois()}.jsonl",
                [json.dumps(e, ensure_ascii=False) for e in utiles],
                "data: journal des marchés",
            )
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
