"""Liens : résolution Google News, lien traduit (spec § 6.3, décision V41)."""

from __future__ import annotations

import json
import re
from urllib.parse import quote, urlsplit

from veille.http import ErreurReseau

DOMAINES_SANS_TRADUCTION = re.compile(
    r"(^|\.)(finextra\.com|ft\.com|wsj\.com|bloomberg\.com|americanbanker\.com)$", re.I
)
_ARABE = re.compile(r"[؀-ۿ]")
BATCHEXECUTE = "https://news.google.com/_/DotsSplashUi/data/batchexecute"


def est_google_news(url: str) -> bool:
    return urlsplit(url).netloc.lower() == "news.google.com"


def detecter_langue(texte: str, defaut: str) -> str:
    """Article en arabe si le titre est majoritairement en caractères arabes."""
    lettres = [c for c in texte if c.isalpha()]
    if lettres and sum(1 for c in lettres if _ARABE.match(c)) / len(lettres) > 0.3:
        return "ar"
    return defaut


# --- Google News ------------------------------------------------------------------------


def resoudre_google_news(client, url: str, journal=None) -> str | None:
    """Résout un lien `news.google.com/rss/articles/…` vers l'URL de l'article.

    Les identifiants actuels ne se décodent plus hors ligne (jeton opaque). Méthode : la page
    de l'article fournit une signature et un horodatage, qu'un appel `batchexecute` échange
    contre l'URL réelle. Point d'accès non documenté de Google, utilisé avec l'accord du
    porteur (14/11/2026) ; en cas d'échec on renvoie None et l'article n'est pas publié.
    """
    m = re.search(r"/articles/([^/?#]+)", url)
    if not m:
        return None
    ident = m.group(1)
    try:
        page = client.get(f"https://news.google.com/rss/articles/{ident}", essais=2)
        signature = re.search(r'data-n-a-sg="([^"]+)"', page.text)
        horodatage = re.search(r'data-n-a-ts="([^"]+)"', page.text)
        if page.status_code != 200 or not signature or not horodatage:
            raise ValueError(f"page d'article inexploitable (HTTP {page.status_code})")
        interne = json.dumps(
            [
                "garturlreq",
                [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None,
                  None, None, 0, 1],
                 "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
                ident,
                int(horodatage.group(1)),
                signature.group(1),
            ],
            separators=(",", ":"),
        )  # fmt: skip
        requete = json.dumps([[["Fbv4je", interne, None, "generic"]]], separators=(",", ":"))
        r = client.post(
            BATCHEXECUTE,
            data="f.req=" + quote(requete),
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
            essais=2,
        )
        reel = json.loads(json.loads(r.text.split("\n\n")[1])[0][2])[1]
    except (ErreurReseau, ValueError, IndexError, KeyError, TypeError) as exc:
        if journal:
            journal.avertir("gnews_resolution_echec", str(exc)[:200], lien=url[:80])
        return None
    if not isinstance(reel, str) or not reel.startswith("http") or est_google_news(reel):
        return None
    return reel


# --- Lien traduit -----------------------------------------------------------------------


def lien_traduit(url: str, langue: str, payant: bool) -> str | None:
    """Lien vers la traduction française automatique de Google (aucun appel d'API, aucun texte
    reproduit). Rien pour le français, les sources payantes et les domaines qui bloquent."""
    if langue == "fr" or payant or est_google_news(url):
        return None
    p = urlsplit(url)
    if not p.netloc or DOMAINES_SANS_TRADUCTION.search(p.hostname or ""):
        return None
    hote = p.netloc.replace("-", "--").replace(".", "-")
    suite = f"{p.query}&" if p.query else ""
    return (
        f"https://{hote}.translate.goog{p.path or '/'}"
        f"?{suite}_x_tr_sl={langue}&_x_tr_tl=fr&_x_tr_hl=fr"
    )


def lien_traduit_repli(url: str, langue: str) -> str:
    """Forme de repli si `translate.goog` échoue pour un hôte (spec § 6.3)."""
    return f"https://translate.google.com/translate?sl={langue}&tl=fr&u={quote(url, safe='')}"
