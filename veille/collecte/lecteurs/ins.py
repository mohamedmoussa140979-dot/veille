"""Lecteur INS : communiqués de presse (titre, date `jj-mm-aaaa`, résumé d'une ligne)."""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from veille.collecte.article import Article, depuis_source, nettoyer_espaces
from veille.collecte.dates import lire_date

MAX_ARTICLES = 60  # la page liste toute l'histoire (plus de mille publications)


def lire_ins(contenu: bytes, source: dict) -> list[Article]:
    soupe = BeautifulSoup(contenu, "lxml")
    articles: dict[str, Article] = {}
    for ligne in soupe.select("div.views-row"):
        lien = ligne.select_one(".views-field-title a[href*='/publication/']")
        if not lien:
            continue
        url = urljoin(source["url"], lien["href"])
        date = ligne.select_one(".views-field-field-date-edition .date")
        resume = ligne.select_one(".views-field-field-resume-pub .field-content")
        articles.setdefault(
            url,
            depuis_source(
                source,
                lien.get_text(" "),
                url,
                publie_le=lire_date(date.get_text(" ") if date else None),
                resume=nettoyer_espaces(resume.get_text(" ")) if resume else "",
            ),
        )
        if len(articles) >= MAX_ARTICLES:
            break
    return list(articles.values())
