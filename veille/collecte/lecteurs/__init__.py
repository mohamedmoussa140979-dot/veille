"""Lecteurs de sources : une fonction par type, `(contenu: bytes, source: dict) -> list[Article]`.

Les lecteurs ne font aucun accès réseau (testés sur des pages enregistrées) ; la récupération
des pages est faite par l'orchestrateur. Une page lisible mais sans aucun article lève
`ErreurLecture` : c'est le signe d'une page qui a changé, jamais un « zéro nouveauté ».
"""

from __future__ import annotations

from collections.abc import Callable

from veille.collecte.article import Article


class ErreurLecture(Exception):
    pass


def _registre() -> dict[str, Callable[[bytes, dict], list[Article]]]:
    from veille.collecte.lecteurs.bct import lire_bct
    from veille.collecte.lecteurs.bvmt import lire_bvmt
    from veille.collecte.lecteurs.cmf import lire_cmf
    from veille.collecte.lecteurs.google_news import lire_google_news
    from veille.collecte.lecteurs.html_generique import lire_html
    from veille.collecte.lecteurs.ins import lire_ins
    from veille.collecte.lecteurs.rss import lire_rss

    return {
        "rss": lire_rss,
        "google-news": lire_google_news,
        "html-generique": lire_html,
        "bct": lire_bct,
        "ins": lire_ins,
        "cmf": lire_cmf,
        "bvmt": lire_bvmt,
    }


def lire(source: dict, contenu: bytes) -> list[Article]:
    lecteur = _registre()[source["type"]]
    articles = lecteur(contenu, source)
    if not articles:
        raise ErreurLecture(f"{source['id']} : page lue mais aucun article reconnu")
    return articles
