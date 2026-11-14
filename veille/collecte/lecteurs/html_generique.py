"""Lecteur HTML générique : liens du même site dont le texte ressemble à un titre.

Repris de `get_articles` de l'ancien `monitor.py`. Sert aux sites sans flux exploitable (presse
tunisienne). Pas de date : l'orchestrateur date l'article à sa première observation.
"""

from __future__ import annotations

from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from veille.collecte.article import Article, depuis_source, nettoyer_espaces

LONGUEUR_MIN_TITRE = 30
MAX_ARTICLES = 80
TITRES_IGNORES = ("Information économique et financière", "Bloomberg LEI")


def _domaine(url: str) -> str:
    return urlsplit(url).netloc.lower().removeprefix("www.")


def lire_html(contenu: bytes, source: dict) -> list[Article]:
    soupe = BeautifulSoup(contenu, "lxml")
    base = source["url"]
    articles: dict[str, Article] = {}
    for a in soupe.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "javascript:", "tel:", "#")):
            continue
        url = urljoin(base, href).split("#")[0]
        if _domaine(url) != _domaine(base) or url.rstrip("/") == base.rstrip("/"):
            continue
        titre = nettoyer_espaces(a.get_text(" "))
        if not titre and url.lower().endswith(".pdf"):
            titre = url.rsplit("/", 1)[-1].rsplit(".", 1)[0].replace("_", " ")
        if len(titre) < LONGUEUR_MIN_TITRE or titre in TITRES_IGNORES:
            continue
        articles.setdefault(url, depuis_source(source, titre[:200], url))
    return list(articles.values())[:MAX_ARTICLES]
