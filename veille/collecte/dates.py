"""Lecture des dates des sources (formats tunisiens et ISO) ; tout est rendu en heure de Tunis."""

from __future__ import annotations

import re
from datetime import datetime

from veille.temps import TUNIS

MOIS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "décembre": 12, "decembre": 12,
}  # fmt: skip

_ISO = re.compile(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:[+-]\d{2}:?\d{2}|Z)?)?")
_NUMERIQUE = re.compile(r"(?<!\d)(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})(?:\s+(\d{1,2}):(\d{2}))?")
_LITTERALE = re.compile(r"(?<!\d)(\d{1,2})(?:er)?[\s\xa0]+([A-Za-zéèêûôàç]+)[\s\xa0]+(\d{4})")


def _construire(a: int, m: int, j: int, h: int = 0, mi: int = 0) -> str | None:
    try:
        return datetime(a, m, j, h, mi, tzinfo=TUNIS).isoformat()
    except ValueError:
        return None


def en_iso_tunis(instant: datetime) -> str:
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=TUNIS)
    return instant.astimezone(TUNIS).isoformat()


def lire_date(texte: str | None) -> str | None:
    """Renvoie une date ISO 8601 à l'heure de Tunis, ou None si le texte n'en contient pas."""
    if not texte:
        return None
    m = _ISO.search(texte)
    if m:
        brut = m.group(0).replace("Z", "+00:00").replace(" ", "T")
        try:
            return en_iso_tunis(datetime.fromisoformat(brut))
        except ValueError:
            pass
    m = _NUMERIQUE.search(texte)
    if m:
        j, mo, a, h, mi = m.groups()
        return _construire(int(a), int(mo), int(j), int(h or 0), int(mi or 0))
    m = _LITTERALE.search(texte)
    if m and m.group(2).lower() in MOIS:
        return _construire(int(m.group(3)), MOIS[m.group(2).lower()], int(m.group(1)))
    return None
