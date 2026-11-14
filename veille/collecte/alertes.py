"""Alertes 🔔 (spec § 5, V9) : régulateurs et agences, plage silencieuse 22:00–07:00 (Tunis)."""

from __future__ import annotations

import html
from datetime import datetime, timedelta

from veille import temps
from veille.collecte.article import Article
from veille.telegram import echapper

AGE_MAX_ALERTE = timedelta(days=7)  # une publication plus ancienne n'est pas une alerte
MAX_PAR_MESSAGE = 15
DEBUT_SILENCE, FIN_SILENCE = 22, 7  # heures de Tunis


def en_plage_silencieuse(instant: datetime) -> bool:
    h = temps.en_tunis(instant).hour
    return h >= DEBUT_SILENCE or h < FIN_SILENCE


def eligibles(
    nouveaux: list[Article], sources: dict[str, dict], maintenant: datetime
) -> list[Article]:
    """Nouveaux articles des sources `alerte: oui`, récents, un seul par fait (groupe)."""
    retenus, groupes = [], set()
    for a in nouveaux:
        if not sources.get(a.source_id, {}).get("alerte"):
            continue
        if a.publie_le and maintenant - datetime.fromisoformat(a.publie_le) > AGE_MAX_ALERTE:
            continue
        cle = a.groupe or a.id
        if cle in groupes:
            continue
        groupes.add(cle)
        retenus.append(a)
    return retenus


def _ligne(a: dict) -> str:
    verrou = "🔒 " if a.get("payant") else ""
    langue = f" [{a['langue'].upper()}]" if a.get("langue", "fr") != "fr" else ""
    ligne = (
        f"<b>{echapper(a['source'])}</b>{langue}\n"
        f'{verrou}<a href="{html.escape(a["url"], quote=True)}">{echapper(a["titre"])}</a>'
    )
    if a.get("url_traduite"):
        ligne += f' (<a href="{html.escape(a["url_traduite"], quote=True)}">FR</a>)'
    return ligne


def construire_message(alertes: list[dict], differe: bool = False) -> str:
    """Corps HTML d'un message d'alerte (l'en-tête 🔔 est ajouté par `telegram.envoyer`)."""
    tete = ""
    if differe:
        tete = (
            f"Détectées pendant la plage silencieuse ({DEBUT_SILENCE}:00–0{FIN_SILENCE}:00) :\n\n"
        )
    lignes = [_ligne(a) for a in alertes[:MAX_PAR_MESSAGE]]
    reste = len(alertes) - MAX_PAR_MESSAGE
    if reste > 0:
        lignes.append(f"… et {reste} autre(s) alerte(s) (voir l'archive du jour).")
    return tete + "\n\n".join(lignes)
