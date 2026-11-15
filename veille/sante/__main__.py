"""Contrôle de santé : `python -m veille.sante [--a-blanc] [--dimanche]` (21:00 Tunis, § 10).

Un message ⚠️ groupé seulement en cas d'anomalie ; le dimanche, un message « ✅ Semaine complète »
même sans anomalie.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta

import yaml

from veille import temps
from veille.config import RACINE, charger_parametres, charger_sources
from veille.etat import EtatGit, EtatLocal
from veille.http import Client, ErreurReseau
from veille.journal import Journal
from veille.marches import mizeniti
from veille.sante import controle
from veille.sante.message import message_anomalies, message_semaine_complete, phrase_semaine
from veille.telegram import envoyer


def charger_evenements(etat, maintenant: datetime) -> list[dict]:
    """Événements de `sante/` des dernières 24 h (mois courant et précédent)."""
    mois = {temps.mois(maintenant), temps.mois(maintenant - timedelta(days=2))}
    evenements = []
    for m in sorted(mois):
        for ligne in (etat.lire(f"sante/{m}.jsonl") or "").splitlines():
            try:
                e = json.loads(ligne)
                if maintenant - datetime.fromisoformat(e["t"]) <= timedelta(hours=24):
                    evenements.append(e)
            except (ValueError, KeyError):
                continue
    return evenements


def runs_github(client, depot: str, token: str, maintenant: datetime, journal) -> list[dict]:
    """Exécutions de workflows des 2 derniers jours (API GitHub, jeton du workflow)."""
    depuis = (maintenant - timedelta(days=3)).date().isoformat()
    try:
        r = client.get(
            f"https://api.github.com/repos/{depot}/actions/runs",
            params={"per_page": 100, "created": f">={depuis}"},
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            essais=2,
        )
        if r.status_code != 200:
            raise ErreurReseau(f"HTTP {r.status_code}")
        return r.json()["workflow_runs"]
    except (ErreurReseau, ValueError, KeyError) as exc:
        journal.avertir("sante_api_github", str(exc)[:120])
        return []


def jours_feries() -> set[str]:
    f = RACINE / "config" / "jours_feries.yaml"
    return {
        str(j)
        for j in (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("jours_feries", [])
    }


def date_bourse(client, base: str, journal) -> str | None:
    donnees = mizeniti._json(client, base, "/marche/bourse/indices.json", journal)
    indices = (donnees or {}).get("indices") or []
    return next((i["date"] for i in indices if i["code"] == "TUNINDEX"), None)


def rassembler(etat, client, journal, maintenant: datetime, params: dict, runs: list[dict]):
    """Toutes les anomalies du § 10 et les chiffres de la semaine."""
    sources = [s for s in charger_sources() if s["actif"]]
    stats = etat.lire_json("state/sources.json", {})
    evenements = charger_evenements(etat, maintenant)
    plafond = float(
        os.environ.get("CLAUDE_PLAFOND_USD_MOIS") or params["claude"]["plafond_usd_mois"]
    )
    attendue = controle.dernier_jour_ouvre(maintenant, jours_feries())
    anomalies = (
        controle.controle_sources(sources, stats, maintenant)
        + controle.controle_taches(runs, maintenant)
        + controle.controle_editions(set(etat.lister("editions")), maintenant)
        + controle.controle_ia(
            evenements, etat.lire_json("state/claude.json", {}), plafond, maintenant
        )
        + controle.controle_donnees(
            evenements, date_bourse(client, params["marches"]["mizeniti_url"], journal), attendue
        )
    )
    limite = (temps.en_tunis(maintenant).date() - timedelta(days=6)).isoformat()
    editions = sum(
        1
        for f in etat.lister("editions")
        if f.split("/")[-1][:10] >= limite and f.endswith(".json")
    )
    alertes = sum(
        n for j, n in etat.lire_json("state/alertes_stats.json", {}).items() if j >= limite
    )
    return anomalies, editions, alertes


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    a_blanc = "--a-blanc" in argv
    journal = Journal.depuis_env()
    params = charger_parametres()
    client = Client(journal=journal, essais=params["http"]["essais"])
    etat = (
        EtatLocal("_etat_local")
        if a_blanc
        else EtatGit.depuis_environnement(journal=journal).ouvrir()
    )
    token, chat_id = os.environ.get("TG_TOKEN_VEILLE"), os.environ.get("TG_CHAT_ID")
    maintenant = temps.maintenant()
    runs = []
    if os.environ.get("GITHUB_TOKEN") and os.environ.get("GITHUB_REPOSITORY"):
        runs = runs_github(
            client, os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"], maintenant, journal
        )
    anomalies, editions, alertes = rassembler(etat, client, journal, maintenant, params, runs)
    dimanche = "--dimanche" in argv or temps.en_tunis(maintenant).weekday() == 6

    for a in anomalies:
        print(f"⚠ {a.texte}\n   ➜ {a.action}")
    print(f"{len(anomalies)} anomalie(s) ; semaine : {editions} édition(s), {alertes} alerte(s)")
    messages = []
    if anomalies:
        semaine = phrase_semaine(editions, alertes) if dimanche else None
        messages.append(("sante", message_anomalies(anomalies, semaine)))
    elif dimanche:
        messages.append(("sante_ok", message_semaine_complete(editions, alertes)))
    code = 0
    if token and chat_id and not a_blanc:
        for type_, corps in messages:
            try:
                envoyer(type_, corps, token=token, chat_id=chat_id, client=client, journal=journal)
            except Exception as exc:  # noqa: BLE001
                journal.erreur("sante_telegram_echec", journal.masquer(str(exc))[:200])
                code = 1
    journal.info(
        "sante_controle", f"{len(anomalies)} anomalie(s)", editions=editions, alertes=alertes
    )
    if not a_blanc:
        lignes = [
            json.dumps(e, ensure_ascii=False)
            for e in journal.evenements
            if e["niveau"] != "info" or e["code"] == "sante_controle"
        ]
        etat.ajouter_lignes(f"sante/{temps.mois()}.jsonl", lignes, "data: contrôle de santé")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
