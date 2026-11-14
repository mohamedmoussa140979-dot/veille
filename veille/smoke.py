"""Essai réel du socle (workflow manuel `smoke`). N'affiche jamais un secret.

Usage : python -m veille.smoke [--claude]
  --claude : fait un appel Claude minimal (quelques millièmes de dollar) pour valider la requête.
"""

from __future__ import annotations

import os
import sys

from veille import temps
from veille.config import charger_parametres
from veille.etat import EtatGit
from veille.http import Client, ErreurReseau
from veille.ia import Gemini, Ia
from veille.journal import Journal
from veille.telegram import envoyer


def etape(titre: str) -> None:
    print(f"\n=== {titre}")


def message_long() -> str:
    blocs = []
    for i in range(1, 41):
        blocs.append(
            f"<b>Sujet d'essai {i}</b>\n"
            f'• <a href="https://example.org/essai/{i}?id={i}&amp;x=2">Lien de l\'article {i}</a>'
            f" (FR)\n" + "Phrase d'essai rédigée pour remplir le message. " * 4
        )
    return "\n\n".join(blocs)


def main(argv: list[str]) -> int:
    avec_claude = "--claude" in argv
    journal = Journal.depuis_env()
    params = charger_parametres()
    client = Client(
        essais=params["http"]["essais"],
        delai_hote=params["http"]["delai_hote_s"],
        journal=journal,
    )
    echecs: list[str] = []

    etape("1. État sur la branche data (création si absente, écriture, relecture)")
    etat = None
    try:
        etat = EtatGit.depuis_environnement("_data", journal=journal).ouvrir()
        horodatage = temps.en_tunis(temps.maintenant()).isoformat()
        etat.modifier_json(
            "state/smoke.json", lambda d: {**d, "dernier_essai": horodatage}, defaut={}
        )
        relu = etat.synchroniser().lire_json("state/smoke.json", {})
        assert relu.get("dernier_essai") == horodatage, "relecture différente de l'écriture"
        print("OK : état écrit et relu sur la branche data")
    except Exception as exc:  # noqa: BLE001 - on veut tout rapporter, jamais de secret
        echecs.append(f"état : {journal.masquer(str(exc))}")

    etape("2. Gemini : découverte des modèles et appel minimal")
    try:
        cle = os.environ.get("GEMINI_API_KEY")
        if not cle:
            raise RuntimeError("GEMINI_API_KEY absente")
        gemini = Gemini(cle, client, journal, attentes=tuple(params["gemini"]["attentes_s"]))
        print("Modèles retenus (ordre d'essai) :", ", ".join(gemini.modeles()))
        texte, modele = gemini.generer("Réponds uniquement par le mot : OK")
        print(f"OK : modèle {modele}, réponse de {len(texte)} caractères")
    except Exception as exc:  # noqa: BLE001
        echecs.append(f"gemini : {journal.masquer(str(exc))}")

    etape("3. Claude : validité de la clé" + (" et appel minimal" if avec_claude else ""))
    try:
        cle = os.environ.get("ANTHROPIC_API_KEY")
        if not cle:
            raise RuntimeError("ANTHROPIC_API_KEY absente")
        r = client.get(
            "https://api.anthropic.com/v1/models",
            headers={"x-api-key": cle, "anthropic-version": "2023-06-01"},
            essais=1,
        )
        print(f"GET /v1/models : HTTP {r.status_code}")
        if r.status_code != 200:
            raise RuntimeError(f"clé Claude non acceptée (HTTP {r.status_code})")
        if avec_claude:
            ia = Ia.depuis_environnement(params, client, journal, etat=etat)
            res = ia.claude.generer("Réponds uniquement par le mot : OK", max_tokens=64)
            print(f"OK : {res.modele} a répondu ({len(res.texte)} caractères)")
            print("Compteur du mois :", ia.claude.compteur.depense(temps.mois()), "USD")
    except Exception as exc:  # noqa: BLE001
        echecs.append(f"claude : {journal.masquer(str(exc))}")

    etape("4. Telegram : message court puis message long découpé")
    try:
        token, chat = os.environ.get("TG_TOKEN_VEILLE"), os.environ.get("TG_CHAT_ID")
        if not token or not chat:
            raise RuntimeError("TG_TOKEN_VEILLE ou TG_CHAT_ID absent")
        r1 = envoyer(
            "test",
            "Socle V0 : essai de connexion. Si vous lisez ceci, le bot fonctionne.",
            token=token,
            chat_id=chat,
            client=client,
            journal=journal,
            silencieux=True,
        )
        r2 = envoyer(
            "test",
            message_long(),
            token=token,
            chat_id=chat,
            client=client,
            journal=journal,
            silencieux=True,
        )
        print(f"OK : message court ({r1.parties} partie), message long ({r2.parties} parties)")
        if r1.repli_texte or r2.repli_texte:
            echecs.append("telegram : repli en texte brut utilisé (le HTML a été refusé)")
    except Exception as exc:  # noqa: BLE001
        echecs.append(f"telegram : {journal.masquer(str(exc))}")

    etape("5. Journal vers la branche data")
    try:
        if etat is None:
            raise RuntimeError("état indisponible")
        etat.ajouter_lignes(f"sante/{temps.mois()}.jsonl", journal.vers_jsonl().splitlines())
        print("OK : journal de l'essai écrit sur data")
    except Exception as exc:  # noqa: BLE001
        echecs.append(f"journal : {journal.masquer(str(exc))}")

    etape("Bilan")
    if echecs:
        for e in echecs:
            print("ÉCHEC", e)
        return 1
    print("Tout est vert.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except ErreurReseau as exc:
        print("ÉCHEC réseau :", exc)
        sys.exit(1)
