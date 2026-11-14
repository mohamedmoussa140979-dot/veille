"""Lecteur CMF (site Drupal) : les éléments sont dans `div.view-content > div.views-row`.

Le reste de la page (menus, raccourcis) n'est pas de l'actualité : l'ancien lecteur générique
le comptait à tort comme « articles ».
"""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from veille.collecte.article import Article, depuis_source
from veille.collecte.dates import lire_date
from veille.collecte.liens import detecter_langue


def lire_cmf(contenu: bytes, source: dict) -> list[Article]:
    soupe = BeautifulSoup(contenu, "lxml")
    articles: dict[str, Article] = {}
    for ligne in soupe.select("div.view-content div.views-row"):
        lien = ligne.select_one("h2 a[href], .field-name-title a[href]")
        if not lien:
            continue
        url = urljoin(source["url"], lien["href"])
        date = ligne.select_one("span.date-display-single")
        texte_date = (date.get("content") or date.get_text(" ")) if date else None
        titre = lien.get_text(" ")
        articles.setdefault(
            url,
            depuis_source(
                source,
                titre,
                url,
                publie_le=lire_date(texte_date),
                langue=detecter_langue(titre, source["langue"]),
            ),
        )
    return list(articles.values())
