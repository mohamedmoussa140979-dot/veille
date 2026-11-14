"""Chargement et validation de la configuration (spec § 6.2)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import jsonschema
import yaml

RACINE = Path(__file__).resolve().parent.parent
TYPES_SOURCE = ["rss", "html-generique", "bct", "ins", "cmf", "bvmt", "google-news"]
CHAPITRES = ["eco-tunisie", "bourse-entreprises", "international", "afrique", "technologie"]

SCHEMA_SOURCES = {
    "type": "object",
    "required": ["sources"],
    "properties": {
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "id", "nom", "url", "type", "chapitre", "langue", "alerte", "payant", "actif"
                ],
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"},
                    "nom": {"type": "string", "minLength": 1},
                    "url": {"type": "string", "pattern": "^https?://"},
                    "type": {"enum": TYPES_SOURCE},
                    "chapitre": {"enum": CHAPITRES},
                    "langue": {"enum": ["fr", "en", "ar"]},
                    "alerte": {"type": "boolean"},
                    "payant": {"type": "boolean"},
                    "actif": {"type": "boolean"},
                },
            },
        }
    },
}  # fmt: skip


class ErreurConfig(Exception):
    pass


def _lire_yaml(chemin: Path) -> Any:
    try:
        return yaml.safe_load(Path(chemin).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ErreurConfig(f"{chemin} illisible : {exc}") from exc


def charger_sources(chemin: Path = RACINE / "config" / "sources.yaml") -> list[dict]:
    donnees = _lire_yaml(chemin)
    try:
        jsonschema.validate(donnees, SCHEMA_SOURCES)
    except jsonschema.ValidationError as exc:
        champ = ".".join(str(p) for p in exc.absolute_path)
        raise ErreurConfig(f"{chemin} : {champ or 'racine'} : {exc.message}") from exc
    ids = [s["id"] for s in donnees["sources"]]
    doublons = sorted({i for i in ids if ids.count(i) > 1})
    if doublons:
        raise ErreurConfig(f"{chemin} : identifiants en double : {', '.join(doublons)}")
    return donnees["sources"]


def charger_exclusions(chemin: Path = RACINE / "config" / "exclusions.yaml") -> list[str]:
    donnees = _lire_yaml(chemin) or {}
    mots = donnees.get("mots_exclus") or []
    if not all(isinstance(m, str) and m.strip() for m in mots):
        raise ErreurConfig(f"{chemin} : mots_exclus doit être une liste de textes non vides")
    return mots


def charger_parametres(chemin: Path = RACINE / "config" / "parametres.yaml") -> dict:
    p = _lire_yaml(chemin)
    brut = os.environ.get("CLAUDE_PLAFOND_USD_MOIS")
    if brut:
        try:
            p["claude"]["plafond_usd_mois"] = float(brut)
        except ValueError as exc:
            raise ErreurConfig(f"CLAUDE_PLAFOND_USD_MOIS n'est pas un nombre : {brut!r}") from exc
    return p
