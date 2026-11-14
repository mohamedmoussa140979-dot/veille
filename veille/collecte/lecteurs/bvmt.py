"""Lecteur BVMT : cartes « avis et décisions » et « publications des sociétés »."""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from veille.collecte.article import Article, depuis_source
from veille.collecte.dates import lire_date


def lire_bvmt(contenu: bytes, source: dict) -> list[Article]:
    soupe = BeautifulSoup(contenu, "lxml")
    articles: dict[str, Article] = {}
    for carte in soupe.select("a.card-link[href]"):
        titre = carte.select_one("h3, h5.event-title, .event-title")
        if not titre:
            continue
        url = urljoin(source["url"], carte["href"])
        date = carte.select_one(".date, span.color-orange")  # pas la date citée dans le titre
        articles.setdefault(
            url,
            depuis_source(
                source,
                titre.get_text(" "),
                url,
                publie_le=lire_date(date.get_text(" ") if date else None),
            ),
        )
    return list(articles.values())
