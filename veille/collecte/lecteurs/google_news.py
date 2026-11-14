"""Lecteur des flux de recherche Google News : titre débarrassé du suffixe « - Média »."""

from __future__ import annotations

from veille.collecte.article import Article, depuis_source, nettoyer_espaces
from veille.collecte.lecteurs.rss import date_entree, entrees


def lire_google_news(contenu: bytes, source: dict) -> list[Article]:
    articles = []
    for e in entrees(contenu, source):
        titre, lien = nettoyer_espaces(e.get("title")), (e.get("link") or "").strip()
        media = e.get("source") or {}
        nom_media = nettoyer_espaces(media.get("title"))
        suffixe = f" - {nom_media}"
        if nom_media and titre.endswith(suffixe):
            titre = titre[: -len(suffixe)].rstrip()
        if titre and lien.startswith("http"):
            articles.append(
                depuis_source(
                    source,
                    titre,
                    lien,
                    publie_le=date_entree(e),
                    media_url=media.get("href"),
                )
            )
            if nom_media:
                articles[-1].source = nom_media  # affichage : « Reuters », pas le nom de la requête
    return articles
