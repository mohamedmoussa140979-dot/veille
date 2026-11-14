"""Premier filtre éditorial (spec § 3) : mots exclus sur titre et résumé, avant tout appel IA."""

from __future__ import annotations

import re
import unicodedata

from veille.collecte.article import Article


def normaliser(texte: str) -> str:
    """Minuscules, sans accents, apostrophes uniformisées."""
    t = (texte or "").lower().replace("’", "'").replace("ʼ", "'")
    t = unicodedata.normalize("NFD", t)
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _compiler(mots: list[str]) -> re.Pattern | None:
    if not mots:
        return None
    mots = sorted({normaliser(m) for m in mots}, key=len, reverse=True)
    return re.compile(r"(?<!\w)(" + "|".join(re.escape(m) for m in mots) + r")(?!\w)")


class Filtre:
    def __init__(self, regles: dict):
        self._categories = {
            nom: _compiler(mots) for nom, mots in regles["mots_exclus"].items() if mots
        }
        self._conservees = [normaliser(e) for e in regles.get("expressions_conservees", [])]
        self._segments = [normaliser(s) for s in regles.get("segments_url_exclus", [])]

    def motif_rejet(self, article: Article, source: dict) -> str | None:
        """Motif du rejet, ou None si l'article passe (sources `filtre: non` : toujours)."""
        if source.get("filtre", True) is False:
            return None
        texte = normaliser(f"{article.titre} {article.resume}")
        if any(e in texte for e in self._conservees):
            return None
        url = normaliser(article.url)
        for segment in self._segments:
            if segment in url:
                return f"url {segment}"
        for categorie, motif in self._categories.items():
            m = motif.search(texte) if motif else None
            if m:
                return f"{categorie}: {m.group(1)}"
        return None
