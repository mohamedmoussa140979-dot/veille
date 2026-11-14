"""Construit le site d'archive : `python -m veille.edition.site <dossier_data> <dossier_sortie>`."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from veille import temps
from veille.edition.archive import construire_site
from veille.edition.modele import EditionInvalide, valider_edition


def charger_editions(dossier_data: Path) -> tuple[list[dict], list[str]]:
    editions, ignorees = [], []
    for f in sorted((Path(dossier_data) / "editions").glob("*.json")):
        try:
            e = json.loads(f.read_text(encoding="utf-8"))
            valider_edition(e)
        except (ValueError, EditionInvalide) as exc:
            ignorees.append(f"{f.name} : {exc}")  # une édition invalide n'arrête pas l'archive
            continue
        editions.append(e)
    return editions, ignorees


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):  # absent sous la capture de pytest
        sys.stdout.reconfigure(encoding="utf-8")
    if len(argv) != 2:
        print("usage : python -m veille.edition.site <dossier_data> <dossier_sortie>")
        return 2
    editions, ignorees = charger_editions(Path(argv[0]))
    for message in ignorees:
        print("IGNORÉE", message)
    jour = temps.en_tunis(temps.maintenant()).date()
    fichiers = construire_site(editions, Path(argv[1]), jour)
    print(f"Archive : {len(editions)} édition(s), {len(fichiers)} fichier(s) dans {argv[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
