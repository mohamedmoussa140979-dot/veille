"""Lecteur CMF (site Drupal) : les éléments sont dans `div.view-content > div.views-row`.

Deux formats de lignes :
- avis, communiqués, visas : un titre `h2 > a` et une date ;
- états financiers et indicateurs d'activité : « société · période · exercice » et un PDF, sans
  titre (le titre est composé, le lien est le PDF).

Le reste de la page (menus, raccourcis) n'est pas de l'actualité : l'ancien lecteur générique
le comptait à tort comme « articles ».
"""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from veille.collecte.article import Article, depuis_source, nettoyer_espaces
from veille.collecte.dates import lire_date
from veille.collecte.liens import detecter_langue

_SOCIETE = ".field-name-field-societesape, .field-name-field-soci-t-"
_PERIODE = ".field-name-field-p-riode, .field-name-field-trimestre"
_EXERCICE = ".field-name-field-exercice, .field-name-field-ann-e-indicateurs"


def _texte(ligne: Tag, selecteur: str) -> str:
    el = ligne.select_one(selecteur)
    return nettoyer_espaces(el.get_text(" ")) if el else ""


def _titre_et_lien(ligne: Tag) -> tuple[str, str | None]:
    lien = ligne.select_one("h2 a[href], .field-name-title a[href]")
    if lien:
        return lien.get_text(" "), lien["href"]
    societe = _texte(ligne, _SOCIETE)
    if not societe:
        return "", None
    periode = " ".join(filter(None, (_texte(ligne, _PERIODE), _texte(ligne, _EXERCICE))))
    pdf = ligne.select_one(".field-type-file a[href]")
    noeud = ligne.select_one("[about]")
    href = pdf["href"] if pdf else (noeud["about"] if noeud else None)
    return f"{societe} – {periode}".strip(" –"), href


def lire_cmf(contenu: bytes, source: dict) -> list[Article]:
    soupe = BeautifulSoup(contenu, "lxml")
    articles: dict[str, Article] = {}
    for ligne in soupe.select("div.view-content div.views-row"):
        titre, href = _titre_et_lien(ligne)
        if not titre or not href:
            continue
        url = urljoin(source["url"], href)
        date = ligne.select_one("span.date-display-single")
        texte_date = (date.get("content") or date.get_text(" ")) if date else None
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
