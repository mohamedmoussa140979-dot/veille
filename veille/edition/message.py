"""Message Telegram d'une édition (spec § 8.1) : l'essentiel, puis les chapitres, puis le lien."""

from __future__ import annotations

import html

from veille.edition.modele import RUBRIQUES
from veille.marches.points import lignes_tableau
from veille.telegram import echapper


def _href(url: str) -> str:
    return html.escape(url, quote=True)


def liens_articles(ids: list[str], articles: dict[str, dict]) -> str:
    """« Source · Source (FR) 🔒 » : un lien par article d'origine, lien traduit après le lien."""
    morceaux = []
    for i in ids:
        a = articles[i]
        m = f'<a href="{_href(a["url"])}">{echapper(a["source"])}</a>'
        if a.get("url_traduite"):
            m += f' (<a href="{_href(a["url_traduite"])}">FR</a>)'
        if a.get("payant"):
            m += " 🔒"
        morceaux.append(m)
    return " · ".join(morceaux)


def construire_message(edition: dict, url_edition: str | None = None) -> str:
    """Corps HTML du message ; l'en-tête 🌅/🌆 est ajouté par `telegram.envoyer`."""
    articles = edition["articles"]
    blocs = ["<b>L'essentiel</b>"]
    for point in edition["essentiel"]:
        blocs.append(
            f"• {echapper(point['texte'])}\n  {liens_articles(point['articles'], articles)}"
        )
    for chapitre in edition["chapitres"]:
        lignes = [f"<b>{echapper(chapitre['titre'])}</b>"]
        if chapitre.get("tableau"):
            lignes += lignes_tableau(chapitre["cle"], chapitre["tableau"])
        for s in chapitre["sujets"]:
            rubrique = RUBRIQUES.get(s.get("rubrique") or "")
            etiquette = f" <i>({echapper(rubrique)})</i>" if rubrique else ""
            liens = liens_articles(s["articles"], articles)
            ligne = f"• <b>{echapper(s['titre'])}</b>{etiquette}\n  {liens}"
            if s.get("impact_menage"):
                ligne += f"\n  🏠 {echapper(s['impact_menage'])}"
            lignes.append(ligne)
        blocs.append("\n".join(lignes))
    if url_edition:
        blocs.append(f'📄 <a href="{_href(url_edition)}">Édition complète</a>')
    return "\n\n".join(blocs)
