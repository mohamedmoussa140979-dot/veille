"""Collecte, score et regroupement des articles de la veille AWB (port de `veille_awb.py`)."""

from __future__ import annotations

import hashlib
import html
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import quote_plus

import feedparser

from veille.http import ErreurReseau

TOLERANCE_FUTUR = timedelta(hours=6)


def gnews_url(requete: str, hl: str, gl: str, ceid: str) -> str:
    return (
        f"https://news.google.com/rss/search?q={quote_plus(requete)}+when:2d"
        f"&hl={hl}&gl={gl}&ceid={ceid}"
    )


def gdelt_url(requete: str, heures: int = 24, langue: str = "english", maximum: int = 75) -> str:
    """GDELT DOC 2.0 : sans clé, renvoie les URL réelles des éditeurs."""
    q = f"{requete} sourcelang:{langue}"
    return (
        "https://api.gdeltproject.org/api/v2/doc/doc"
        f"?query={quote_plus(q)}&mode=artlist&maxrecords={maximum}"
        f"&timespan={heures}h&sort=datedesc&format=rss"
    )


def norm_titre(t: str) -> str:
    t = html.unescape(t or "").lower()
    t = re.sub(r"\s*[-|–—]\s*[^-|–—]{2,40}$", "", t)
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip()


def cle_titre(titre: str) -> str:
    return hashlib.sha1(norm_titre(titre).encode("utf-8")).hexdigest()[:16]


def titre_propre(titre: str, media: str) -> str:
    if media and titre.endswith(" - " + media):
        return titre[: -(len(media) + 3)].strip()
    return re.sub(r"\s+[-|–—]\s+[^-|–—]{2,40}$", "", titre).strip()


def media_de_domaine(lien: str) -> str:
    m = re.match(r"^https?://(?:www\.)?([^/:?#]+)", lien or "")
    if not m:
        return ""
    d = re.sub(r"\.(com|net|org|co\.uk|co|io|fr|ma|tn|eu|info|news)$", "", m.group(1))
    return d.replace(".", " ").replace("-", " ").title()


def resume_utile(titre: str, resume: str) -> bool:
    """Le résumé n'apporte rien s'il reprend le titre (cas Google News)."""
    if not resume or len(resume.strip()) < 60:
        return False
    nt, nr = norm_titre(titre), norm_titre(resume)
    if not nt:
        return True
    if nr.startswith(nt[:60]):
        return False
    mots_t, mots_r = set(nt.split()), set(nr.split())
    return not (mots_t and len(mots_t & mots_r) / len(mots_t) > 0.85)


def cle_evenement(cfg: dict, titre: str, resume: str = "") -> str | None:
    """Regroupe les reprises d'un même événement : acteur × pays (ex. Moody's et la Tunisie)."""
    txt = norm_titre(f"{titre} {resume}")
    acteur = next((k for k, rx in cfg["acteurs"].items() if rx.search(txt)), None)
    pays = next((k for k, rx in cfg["pays"].items() if rx.search(txt)), None)
    return f"ev:{acteur}:{pays}" if acteur and pays else None


def score(cfg: dict, titre: str, resume: str, poids_base: int) -> int:
    txt = f"{titre} {resume}"
    return poids_base + sum(w for rx, w in cfg["signaux"] if rx.search(txt))


def lire_flux(
    contenu: bytes,
    cfg: dict,
    sujet: dict,
    poids: int,
    etiquette: str,
    limite: datetime,
    langue: str,
    maintenant: datetime,
    strict: bool = True,
) -> list[dict]:
    """Articles pertinents d'un flux : filtres de bruit, de source, de motif, fenêtre de temps."""
    items = []
    for e in feedparser.parse(contenu).entries[:40]:
        titre = html.unescape(e.get("title") or "")
        resume = re.sub(r"<[^>]+>", " ", e.get("summary") or "")[:400]
        lien = e.get("link") or ""
        if not titre or not lien:
            continue
        txt = f"{titre} {resume}"
        media = ((e.get("source") or {}).get("title") or "").strip()
        if not media and " - " in titre:
            media = titre.rsplit(" - ", 1)[-1].strip()
        media = media or media_de_domaine(lien) or etiquette
        if cfg["sources_exclues"].search(media) or cfg["publicite"].search(txt):
            continue
        if not sujet["motif"].search(txt):
            continue
        if strict and sujet["motif_et"] and not sujet["motif_et"].search(txt):
            continue
        if cfg["bruit"].search(txt):
            continue
        t = e.get("published_parsed") or e.get("updated_parsed")
        if not t:
            continue  # sans date fiable on écarte : évite les vieux articles
        date = datetime(*t[:6], tzinfo=UTC)
        if date < limite or date > maintenant + TOLERANCE_FUTUR:
            continue
        bonus = 4 if cfg["sources_qualite"].search(media) else 0
        items.append(
            {
                "cle": cle_titre(titre),
                "titre": titre.strip(),
                "lien": lien,
                "resume": resume,
                "tag": sujet["tag"],
                "source": media,
                "date": date,
                "score": score(cfg, titre, resume, poids) + bonus,
                "seuil": sujet["seuil"],
                "langue": langue,
                "evenement": cle_evenement(cfg, titre, resume),
            }
        )
    return items


def recuperer(client, url: str, journal=None, nom: str = "") -> bytes | None:
    """Contenu d'un flux ou None (avertissement) ; une panne n'arrête jamais la collecte."""
    try:
        r = client.get(url, essais=2)
        if r.status_code != 200:
            raise ErreurReseau(f"HTTP {r.status_code}")
        return r.content
    except ErreurReseau as exc:
        if journal:
            journal.avertir("awb_flux_en_erreur", str(exc)[:120], flux=nom)
        return None


def collecter(cfg: dict, client_gnews, client_gdelt, client, maintenant: datetime, journal=None):
    """Tous les articles pertinents des sujets. Renvoie (items, erreurs par type de flux)."""
    items: list[dict] = []
    erreurs = {"gnews": 0, "gdelt": 0, "flux": 0}
    for sujet in cfg["sujets"]:
        limite = maintenant - timedelta(hours=sujet["fenetre_h"])
        for requete, poids in sujet["requetes"].items():
            for hl, gl, ceid in sujet["locales"]:
                contenu = recuperer(
                    client_gnews, gnews_url(requete, hl, gl, ceid), journal, "gnews"
                )
                if contenu is None:
                    erreurs["gnews"] += 1
                    continue
                items += lire_flux(
                    contenu, cfg, sujet, poids, f"GNews {gl}", limite, hl, maintenant
                )
        for requete, poids in (sujet.get("gdelt") or {}).items():
            contenu = recuperer(
                client_gdelt, gdelt_url(requete, sujet["fenetre_h"]), journal, "gdelt"
            )
            if contenu is None:
                erreurs["gdelt"] += 1
                continue
            items += lire_flux(
                contenu, cfg, sujet, poids, "GDELT", limite, "en", maintenant, strict=False
            )
        for f in sujet.get("flux") or []:
            contenu = recuperer(client, f["url"], journal, f["nom"])
            if contenu is None:
                erreurs["flux"] += 1
                continue
            items += lire_flux(
                contenu, cfg, sujet, f["poids"], f["nom"], limite, "en", maintenant, strict=False
            )
    return items, erreurs


def selectionner(cfg: dict, items: list[dict], vus: dict[str, int], maintenant_ts: int):
    """Un article par titre et par événement, jamais déjà vu, au-dessus du seuil de son sujet."""
    uniques: dict[str, dict] = {}
    par_evenement: dict[str, dict] = {}
    fenetre_evt = cfg["fenetre_evenement_h"] * 3600
    for it in items:
        if it["cle"] in vus:
            continue
        ev = it.get("evenement")
        if ev and maintenant_ts - vus.get(ev, 0) < fenetre_evt:
            continue  # événement déjà traité ces derniers jours
        if ev:
            prec = par_evenement.get(ev)
            if prec and prec["score"] >= it["score"]:
                continue
            if prec:
                uniques.pop(prec["cle"], None)
            par_evenement[ev] = it
        if it["cle"] not in uniques or it["score"] > uniques[it["cle"]]["score"]:
            uniques[it["cle"]] = it
    retenus = [it for it in uniques.values() if it["score"] >= it["seuil"]]
    retenus.sort(key=lambda x: (x["tag"], -x["score"], x["date"]))
    return retenus, uniques
