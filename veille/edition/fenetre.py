"""Fenêtre de temps d'une édition (spec § 5) et chargement des articles de cette fenêtre."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from veille import temps

HEURE_MATIN = (7, 30)
FENETRE_PAR_DEFAUT = {"matin": timedelta(hours=14), "soir": timedelta(hours=11)}
FENETRE_WEEKEND = timedelta(hours=24)
FENETRE_MAX = timedelta(hours=72)
CHEMIN_HISTORIQUE = "state/editions.json"


def type_pour(maintenant: datetime) -> str:
    """Type d'édition attendu à cet instant : week-end (09:30), matin (avant 13:00) ou soir."""
    t = temps.en_tunis(maintenant)
    if t.weekday() >= 5:
        return "weekend"
    return "matin" if t.hour < 13 else "soir"


CRONS = {
    "30 6 * * 1-5": "matin",  # 07:30 à Tunis
    "30 17 * * 1-5": "soir",  # 18:30
    "30 8 * * 0,6": "weekend",  # 09:30
}


def type_depuis_cron(cron: str) -> str | None:
    """Type d'édition lié à l'horaire du workflow (fiable même si GitHub retarde l'exécution)."""
    return CRONS.get((cron or "").strip())


def fichier_et_id(type_edition: str, maintenant: datetime) -> tuple[str, str]:
    """(identifiant, type enregistré). Le week-end s'enregistre comme `matin` (le contrat ne
    connaît que `matin` et `soir`)."""
    enregistre = "matin" if type_edition == "weekend" else type_edition
    jour = temps.en_tunis(maintenant).date().isoformat()
    return f"{jour}-{enregistre}", enregistre


def calculer_fenetre(
    type_edition: str, maintenant: datetime, historique: list[dict]
) -> tuple[datetime, datetime]:
    """Du dernier passage d'édition (autre que celle-ci) jusqu'à maintenant."""
    ident, _ = fichier_et_id(type_edition, maintenant)
    fin = maintenant
    if type_edition == "weekend":
        return fin - FENETRE_WEEKEND, fin
    precedentes = [
        datetime.fromisoformat(h["fin"])
        for h in historique
        if h["id"] != ident and datetime.fromisoformat(h["fin"]) < fin
    ]
    debut = max(precedentes) if precedentes else fin - FENETRE_PAR_DEFAUT[type_edition]
    return max(debut, fin - FENETRE_MAX), fin


def charger_articles(etat, debut: datetime, fin: datetime, maximum: int = 400) -> list[dict]:
    """Articles de `articles/AAAA-MM-JJ.jsonl` dont la première observation est dans la fenêtre."""
    jours, jour = [], temps.en_tunis(debut).date()
    while jour <= temps.en_tunis(fin).date():
        jours.append(jour.isoformat())
        jour += timedelta(days=1)
    retenus: dict[str, dict] = {}
    for j in jours:
        for ligne in (etat.lire(f"articles/{j}.jsonl") or "").splitlines():
            if not ligne.strip():
                continue
            a = json.loads(ligne)
            instant = a.get("vu_le") or a.get("publie_le")
            if instant and debut <= datetime.fromisoformat(instant) < fin:
                retenus.setdefault(a["id"], a)
    articles = sorted(retenus.values(), key=lambda a: a.get("publie_le") or "", reverse=True)
    return articles[:maximum]
