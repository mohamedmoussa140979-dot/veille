"""Constantes éditoriales (spec § 4) et validation du fichier d'édition (contrat avec Mizeniti)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema

SCHEMA_CHEMIN = Path(__file__).resolve().parent.parent.parent / "schema" / "edition.v1.json"

# Ordre d'affichage des chapitres (le chapitre 1, « L'essentiel », est un bloc à part).
CHAPITRES = [
    ("eco-tunisie", "Économie tunisienne"),
    ("bourse-entreprises", "Bourse, entreprises et acteurs économiques"),
    ("international", "Économie et marchés internationaux"),
    ("afrique", "Économie africaine"),
    ("technologie", "Technologie"),
]
TITRES = dict(CHAPITRES)
RUBRIQUES = {
    "reglementation": "Réglementation",
    "notations": "Notations",
    "statistiques": "Statistiques et finances publiques",
    "presse": "Revue de la presse économique",
}
MAX_SUJETS = 5
MAX_ESSENTIEL = 5

# Les quatre chiffres de l'en-tête Mizeniti : à `null` jusqu'au lot V3.
CHIFFRES_VIDES = [
    {"cle": "tunindex", "libelle": "TUNINDEX"},
    {"cle": "eur_tnd_bct", "libelle": "EUR/TND (BCT)"},
    {"cle": "brent", "libelle": "Brent"},
    {"cle": "tmm", "libelle": "TMM"},
]


class EditionInvalide(Exception):
    pass


def charger_schema() -> dict:
    return json.loads(SCHEMA_CHEMIN.read_text(encoding="utf-8"))


def valider_edition(edition: dict) -> None:
    """Schéma v1 + règles du § 4 : liens présents, aucun Google News, aucun `utm_`, ids connus."""
    try:
        jsonschema.validate(edition, charger_schema())
    except jsonschema.ValidationError as exc:
        champ = ".".join(str(p) for p in exc.absolute_path) or "racine"
        raise EditionInvalide(f"schéma v1 : {champ} : {exc.message}") from exc
    articles = edition["articles"]
    references = [a for p in edition["essentiel"] for a in p["articles"]]
    references += [a for c in edition["chapitres"] for s in c["sujets"] for a in s["articles"]]
    inconnus = sorted({a for a in references if a not in articles})
    if inconnus:
        raise EditionInvalide(f"articles cités mais absents : {', '.join(inconnus)}")
    for c in edition["chapitres"]:
        if not c["sujets"] and not c["tableau"]:
            raise EditionInvalide(f"chapitre {c['cle']} vide : ni sujet ni tableau")
    ordre = [c for c, _ in CHAPITRES]
    cles = [c["cle"] for c in edition["chapitres"]]
    if cles != sorted(cles, key=ordre.index):
        raise EditionInvalide(f"chapitres dans le désordre : {cles}")
    for ident, a in articles.items():
        for champ in ("url", "url_traduite"):
            url = a.get(champ) or ""
            if "news.google.com" in url:
                raise EditionInvalide(f"{ident} : lien Google News non résolu ({champ})")
            if re.search(r"[?&](utm_[a-z]+|fbclid|gclid)=", url):
                raise EditionInvalide(f"{ident} : paramètre de suivi dans {champ}")
