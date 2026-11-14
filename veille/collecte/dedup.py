"""Déduplication par titre proche : un même fait couvert par plusieurs sources = un groupe."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from veille.collecte.article import Article
from veille.collecte.filtre import normaliser

SEUIL_SIMILARITE = 0.82
SEUIL_JETONS = 0.7
MOTS_VIDES = {
    "les", "des", "une", "dans", "pour", "avec", "sur", "par", "que", "qui", "aux",
    "the", "and", "for", "of", "to", "in",
}  # fmt: skip


def titre_normalise(titre: str) -> str:
    t = re.sub(r"\s+[-|–—]\s+[^-|–—]{2,40}$", "", titre)  # suffixe « - Média »
    return re.sub(r"[^\w\s]", " ", normaliser(t)).strip()


def _jetons(titre_norm: str) -> set[str]:
    return {m for m in titre_norm.split() if len(m) >= 3 and m not in MOTS_VIDES}


def similaires(a: str, b: str) -> bool:
    """Deux titres normalisés désignent-ils le même fait ?"""
    if not a or not b:
        return False
    if a == b:
        return True
    ja, jb = _jetons(a), _jetons(b)
    if len(ja) >= 4 and len(jb) >= 4 and len(ja & jb) / len(ja | jb) >= SEUIL_JETONS:
        return True
    return SequenceMatcher(None, a, b).ratio() >= SEUIL_SIMILARITE


def grouper(articles: list[Article], references: list[tuple[str, str]] | None = None) -> None:
    """Renseigne `groupe` (id du premier article du fait) sur les articles d'un même fait.

    `references` : (id, titre normalisé) des articles des jours précédents (sans modification).
    Un article sans doublon garde `groupe = None`.
    """
    vus: list[tuple[str, str, Article | None]] = [(i, t, None) for i, t in (references or [])]
    for article in articles:
        titre = titre_normalise(article.titre)
        for ref_id, ref_titre, ref_article in vus:
            if similaires(titre, ref_titre):
                if ref_article is not None:
                    ref_article.groupe = ref_article.groupe or ref_article.id
                    article.groupe = ref_article.groupe
                else:
                    article.groupe = ref_id
                break
        vus.append((article.id, titre, article))
