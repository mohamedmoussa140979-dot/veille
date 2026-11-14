"""Modèle d'article, nettoyage et normalisation des URL."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Paramètres de suivi retirés des liens (spec § 6.3).
_SUIVI = re.compile(
    r"^(utm_.*|fbclid|gclid|dclid|msclkid|yclid|mc_cid|mc_eid|igshid|_ga|_gl|ref_src|ref_url|"
    r"ocid|cmpid|xtor|at_.*|wt\.mc_id|s_cid)$",
    re.I,
)


def nettoyer_espaces(texte: str | None) -> str:
    return re.sub(r"\s+", " ", (texte or "").replace("\xa0", " ")).strip()


def nettoyer_url(url: str) -> str:
    """Retire les paramètres de suivi et le fragment ; conserve le reste tel quel."""
    p = urlsplit(url.strip())
    requete = urlencode(
        [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not _SUIVI.match(k)]
    )
    return urlunsplit((p.scheme, p.netloc, p.path, requete, ""))


def cle_url(url: str) -> str:
    """Forme canonique pour la déduplication : sans www, sans « / » final, paramètres triés."""
    p = urlsplit(nettoyer_url(url))
    hote = p.netloc.lower().removeprefix("www.")
    chemin = p.path.rstrip("/") or "/"
    requete = urlencode(sorted(parse_qsl(p.query, keep_blank_values=True)))
    return f"{hote}{chemin}" + (f"?{requete}" if requete else "")


def id_article(url: str) -> str:
    return hashlib.sha1(cle_url(url).encode("utf-8")).hexdigest()[:12]


@dataclass
class Article:
    source_id: str
    source: str
    titre: str
    url: str
    publie_le: str | None = None
    langue: str = "fr"
    payant: bool = False
    resume: str = ""
    chapitre: str = ""
    url_traduite: str | None = None
    titre_origine: str | None = None
    media_url: str | None = None  # site annoncé par Google News, pour contrôler la résolution
    groupe: str | None = None  # identifiant du premier article traitant le même fait

    @property
    def id(self) -> str:
        return id_article(self.url)

    def vers_dict(self) -> dict:
        d = {k: v for k, v in asdict(self).items() if v not in (None, "")}
        d["id"] = self.id
        return d

    @classmethod
    def depuis_dict(cls, d: dict) -> Article:
        champs = cls.__dataclass_fields__
        return cls(**{k: v for k, v in d.items() if k in champs})


def depuis_source(source: dict, titre: str, url: str, **kw) -> Article:
    """Article hérité des réglages de sa source (langue, chapitre, payant)."""
    return Article(
        source_id=source["id"],
        source=source["nom"],
        titre=nettoyer_espaces(titre),
        url=url,
        langue=kw.pop("langue", None) or source["langue"],
        payant=source["payant"],
        chapitre=source["chapitre"],
        **kw,
    )
