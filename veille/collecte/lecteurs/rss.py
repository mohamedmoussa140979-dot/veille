"""Lecteur RSS/Atom (feedparser, tolérant). Sert aussi de base au lecteur Google News."""

from __future__ import annotations

from datetime import UTC, datetime

import feedparser
from bs4 import BeautifulSoup

from veille.collecte.article import Article, depuis_source, nettoyer_espaces
from veille.collecte.dates import en_iso_tunis

MAX_ENTREES = 60


def entrees(contenu: bytes, source: dict) -> list:
    from veille.collecte.lecteurs import ErreurLecture

    flux = feedparser.parse(contenu)
    if not flux.entries:
        raison = "HTML ou XML invalide" if flux.bozo else "flux vide"
        raise ErreurLecture(f"{source['id']} : aucune entrée ({raison})")
    return flux.entries[:MAX_ENTREES]


def date_entree(entree) -> str | None:
    t = entree.get("published_parsed") or entree.get("updated_parsed")
    return en_iso_tunis(datetime(*t[:6], tzinfo=UTC)) if t else None


def resume_entree(entree) -> str:
    brut = entree.get("summary") or ""
    return nettoyer_espaces(BeautifulSoup(brut, "lxml").get_text(" "))[:400]


def lire_rss(contenu: bytes, source: dict) -> list[Article]:
    articles = []
    for e in entrees(contenu, source):
        titre, lien = nettoyer_espaces(e.get("title")), (e.get("link") or "").strip()
        if titre and lien.startswith("http"):
            articles.append(
                depuis_source(
                    source, titre, lien, publie_le=date_entree(e), resume=resume_entree(e)
                )
            )
    return articles
