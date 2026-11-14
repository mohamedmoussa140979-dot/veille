"""Message 🏦 de la veille AWB : un seul message groupé par passage, une section par sujet."""

from __future__ import annotations

import html

from veille import temps
from veille.awb.collecte import resume_utile, titre_propre
from veille.collecte.liens import lien_traduit
from veille.telegram import echapper


def niveau(score: int) -> str:
    return "🔴" if score >= 24 else ("🟠" if score >= 19 else "⚪️")


def _lien(url: str, texte: str) -> str:
    return f'<a href="{html.escape(url, quote=True)}">{texte}</a>'


def article(it: dict, traducteur) -> str:
    """Bloc HTML d'un article : titre en français, titre d'origine, résumé, source, liens."""
    vo = titre_propre(it["titre"], it["source"])
    non_fr = it["langue"] != "fr"
    titre = traducteur.traduire(vo, it["langue"]) if non_fr else vo
    lignes = [f"{niveau(it['score'])} <b>{echapper(titre)}</b>"]
    if non_fr and titre != vo:
        lignes.append(f"<i>{echapper(vo)}</i>")
    brut = (it.get("resume") or "").strip()
    if resume_utile(it["titre"], brut):
        court = brut[:400].rsplit(" ", 1)[0]
        lignes.append(echapper(traducteur.traduire(court, it["langue"]) if non_fr else court))
    date = temps.en_tunis(it["date"]).strftime("%d/%m %H:%M")
    lignes.append(f"<i>{echapper(it['source'])} · {date} · score {it['score']}</i>")
    liens = [_lien(it["lien"], "🔗 Source")]
    traduit = lien_traduit(it["lien"], it["langue"], False) if non_fr else None
    if traduit:
        liens.insert(0, _lien(traduit, "🇫🇷 Lire en français"))
    lignes.append("  ·  ".join(liens))
    return "\n".join(lignes)


def construire_message(items: list[dict], traducteur) -> str:
    """Les articles sont déjà triés par sujet puis par score ; l'en-tête 🏦 est ajouté à l'envoi."""
    blocs, courant = [], None
    for it in items:
        if it["tag"] != courant:
            courant = it["tag"]
            blocs.append(f"<b>{echapper(courant)}</b>")
        blocs.append(article(it, traducteur))
    return "\n\n".join(blocs)
