"""Lecteur BCT : actualités de la page d'accueil et circulaires (`page.jsp?id=226`).

Le flux RSS de la BCT est en maintenance (constat du 14/11) : on ne dépend pas de lui.
"""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from veille.collecte.article import Article, depuis_source, nettoyer_espaces
from veille.collecte.dates import lire_date


def _actualites(soupe: BeautifulSoup, source: dict) -> list[Article]:
    articles: dict[str, Article] = {}
    for bloc in soupe.select("div.slider-content"):
        lien = bloc.select_one("a[href*='actualites.jsp?id=']")
        description = bloc.select_one(".description")
        if not lien or not description:
            continue
        url = urljoin(source["url"], lien["href"])
        date = bloc.select_one(".date")
        articles.setdefault(
            url,
            depuis_source(
                source,
                description.get_text(" "),
                url,
                publie_le=lire_date(date.get_text(" ") if date else None),
            ),
        )
    return list(articles.values())


def _circulaires(soupe: BeautifulSoup, source: dict) -> list[Article]:
    articles: dict[str, Article] = {}
    for lien in soupe.select("li a[href$='.pdf']"):
        titre = nettoyer_espaces(lien.get_text(" "))
        if titre:
            url = urljoin(source["url"], lien["href"])
            # la date figure dans le titre : « … du 30 décembre 2016 »
            articles.setdefault(
                url,
                depuis_source(
                    source,
                    titre,
                    url,
                    publie_le=lire_date(titre),
                    langue="ar" if "en arabe" in titre.lower() else None,
                ),
            )
    return list(articles.values())


def lire_bct(contenu: bytes, source: dict) -> list[Article]:
    soupe = BeautifulSoup(contenu, "lxml")
    if "page.jsp" in source["url"]:
        return _circulaires(soupe, source)
    return _actualites(soupe, source)
