"""Chargement de `config/awb.yaml` : expressions régulières compilées, sujets, signaux de score."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from veille.config import RACINE, ErreurConfig

CHEMIN = RACINE / "config" / "awb.yaml"


def _re(motif: str) -> re.Pattern:
    return re.compile(motif, re.IGNORECASE)


def charger(chemin: Path = CHEMIN) -> dict:
    try:
        brut = yaml.safe_load(Path(chemin).read_text(encoding="utf-8"))
        sujets = []
        for s in brut["sujets"]:
            sujets.append(
                {
                    **s,
                    "locales": [tuple(x) for x in s.get("locales", [])],
                    "motif": _re(s["motif"]),
                    "motif_et": _re(s["motif_et"]) if s.get("motif_et") else None,
                    "seuil": s.get("seuil", brut["seuil_defaut"]),
                    "fenetre_h": s.get("fenetre_h", brut["fenetre_h"]),
                }
            )
        return {
            **brut,
            "sujets": sujets,
            "bruit": _re("|".join(brut["bruit"])),
            "sources_exclues": _re(brut["sources_exclues"]),
            "sources_qualite": _re(brut["sources_qualite"]),
            "publicite": _re(brut["publicite"]),
            "signaux": [(_re(p), w) for p, w in brut["signaux"].items()],
            "acteurs": {k: _re(v) for k, v in brut["evenements"]["acteurs"].items()},
            "pays": {k: _re(v) for k, v in brut["evenements"]["pays"].items()},
        }
    except (OSError, KeyError, re.error, yaml.YAMLError) as exc:
        raise ErreurConfig(f"{chemin} invalide : {exc}") from exc
