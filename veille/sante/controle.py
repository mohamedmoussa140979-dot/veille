"""Contrôles du § 10 de la spec : fonctions pures, testées avec des états simulés (critère A8)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from veille import temps

# Délai de silence au-delà duquel une source est signalée (spec § 10) : presse 3 jours ouvrés,
# INS 10 jours, BCT, CMF et BVMT 7 jours.
SEUIL_PRESSE_JOURS_OUVRES = 3
SEUILS_JOURS = {"ins": 10, "bct": 7, "cmf": 7, "bvmt": 7}
ERREURS_CONSECUTIVES_MAX = 6  # environ une journée de passages en échec

# Plus long silence normal de chaque workflow planifié, en heures (week-ends compris) + marge.
SILENCE_MAX_H = {"collecte": 16, "edition": 25, "marches": 70, "awb": 16}


@dataclass
class Anomalie:
    code: str
    texte: str
    action: str


def jours_ouvres_depuis(depuis: date, jusqu_a: date) -> int:
    """Nombre de jours ouvrés (lundi-vendredi) dans l'intervalle ]depuis, jusqu_a]."""
    n, jour = 0, depuis + timedelta(days=1)
    while jour <= jusqu_a:
        n += jour.weekday() < 5
        jour += timedelta(days=1)
    return n


def _jour(iso: str | None) -> date | None:
    return temps.en_tunis(datetime.fromisoformat(iso)).date() if iso else None


def controle_sources(sources: list[dict], stats: dict, maintenant: datetime) -> list[Anomalie]:
    """Sources sans aucun nouvel article au-delà de leur délai, ou illisibles depuis longtemps."""
    anomalies, aujourdhui = [], temps.en_tunis(maintenant).date()
    for s in sources:
        if not s["actif"]:
            continue
        st = stats.get(s["id"], {})
        if st.get("erreurs_consecutives", 0) >= ERREURS_CONSECUTIVES_MAX:
            anomalies.append(
                Anomalie(
                    f"source_illisible:{s['id']}",
                    f"{s['nom']} illisible depuis {st['erreurs_consecutives']} passages "
                    f"({st.get('derniere_erreur', 'erreur inconnue')[:80]})",
                    "ouvrir la page dans un navigateur : le site a peut-être changé ou bloque GitHub",
                )
            )
            continue
        derniere = _jour(st.get("dernier_nouvel_article")) or _jour(st.get("premier_passage"))
        if derniere is None:
            continue  # pas encore observée : rien à reprocher
        if s["type"] in SEUILS_JOURS:
            silence, limite, unite = (aujourdhui - derniere).days, SEUILS_JOURS[s["type"]], "jours"
        else:
            silence = jours_ouvres_depuis(derniere, aujourdhui)
            limite, unite = SEUIL_PRESSE_JOURS_OUVRES, "jours ouvrés"
        if silence >= limite:
            anomalies.append(
                Anomalie(
                    f"source_muette:{s['id']}",
                    f"{s['nom']} : aucun nouvel article depuis {silence} {unite} "
                    f"(dernier le {derniere.strftime('%d/%m')})",
                    "vérifier la source, ou la mettre en pause (actif: false) dans sources.yaml",
                )
            )
    return anomalies


def controle_taches(runs: list[dict], maintenant: datetime) -> list[Anomalie]:
    """Tâches planifiées en échec dans les dernières 24 h, ou qui ne tournent plus."""
    anomalies = []
    for nom, silence_max in SILENCE_MAX_H.items():
        des_runs = [r for r in runs if r["name"] == nom]
        reussis = [r for r in des_runs if r.get("conclusion") == "success"]
        dernier_ok = max((datetime.fromisoformat(r["created_at"]) for r in reussis), default=None)
        if dernier_ok is None or maintenant - dernier_ok > timedelta(hours=silence_max):
            anomalies.append(
                Anomalie(
                    f"tache_muette:{nom}",
                    f"Le workflow « {nom} » n'a pas réussi depuis plus de {silence_max} h",
                    "ouvrir l'onglet Actions du dépôt ; vérifier le compte GitHub (facturation, quota)",
                )
            )
        for r in des_runs:
            recent = maintenant - datetime.fromisoformat(r["created_at"]) <= timedelta(hours=24)
            # seules les tâches planifiées comptent : un essai manuel raté n'est pas une panne
            planifiee = r.get("event", "schedule") == "schedule"
            if recent and planifiee and r.get("conclusion") == "failure":
                anomalies.append(
                    Anomalie(
                        f"tache_en_echec:{nom}:{r['id']}",
                        f"Le workflow « {nom} » a échoué ({temps.en_tunis(datetime.fromisoformat(r['created_at'])):%d/%m %H:%M})",
                        f"lire le journal : {r['html_url']}",
                    )
                )
    return anomalies


def dernier_jour_ouvre(maintenant: datetime, jours_feries: set[str]) -> date:
    """Dernier jour de séance attendu à 21:00 : aujourd'hui si ouvré, sinon le précédent."""
    jour = temps.en_tunis(maintenant).date()
    while jour.weekday() >= 5 or jour.isoformat() in jours_feries:
        jour -= timedelta(days=1)
    return jour


def controle_editions(fichiers: set[str], maintenant: datetime) -> list[Anomalie]:
    """Édition manquante : matin et soir en semaine, une seule (matin) le week-end."""
    t = temps.en_tunis(maintenant)
    attendues = ["matin"] if t.weekday() >= 5 else ["matin", "soir"]
    return [
        Anomalie(
            f"edition_manquante:{t.date()}-{e}",
            f"Édition {e} du {t:%d/%m} absente",
            "relancer le workflow « edition » (type et heures) ; voir l'alerte ⚠️ de l'édition",
        )
        for e in attendues
        if f"editions/{t.date().isoformat()}-{e}.json" not in fichiers
    ]


def controle_ia(evenements: list[dict], claude: dict, plafond_usd: float, maintenant: datetime):
    """Gemini en échec avec Claude utilisé ; plafond Claude à 80 % ou atteint."""
    codes = {e["code"] for e in evenements}
    anomalies = []
    if "claude_secours_utilise" in codes:
        anomalies.append(
            Anomalie(
                "claude_utilise",
                "Gemini en échec : le secours Claude a été utilisé",
                "vérifier la clé GEMINI_API_KEY et les modèles ; surveiller le plafond mensuel",
            )
        )
    depense = claude.get(temps.mois(maintenant), {}).get("usd", 0.0)
    if "claude_plafond_atteint" in codes or (plafond_usd and depense >= plafond_usd):
        anomalies.append(
            Anomalie(
                "claude_plafond_atteint",
                f"Plafond Claude atteint ({depense:.2f} $ sur {plafond_usd:.2f} $) : synthèses non générées",
                "relever CLAUDE_PLAFOND_USD_MOIS (variable du dépôt) ou attendre le mois suivant",
            )
        )
    elif plafond_usd and depense >= 0.8 * plafond_usd:
        anomalies.append(
            Anomalie(
                "claude_plafond_80",
                f"Plafond Claude à {round(100 * depense / plafond_usd)} % ({depense:.2f} $ sur {plafond_usd:.2f} $)",
                "surveiller ; relever CLAUDE_PLAFOND_USD_MOIS si besoin",
            )
        )
    return anomalies


def controle_donnees(evenements: list[dict], date_bourse: str | None, attendue: date):
    """Yahoo ou traduction AWB sans donnée ; Bourse de Mizeniti plus ancienne que le dernier jour ouvré."""
    codes = [e["code"] for e in evenements]
    anomalies = []
    if "yahoo_echec" in codes or "yahoo_sans_donnee" in codes:
        n = codes.count("yahoo_echec") + codes.count("yahoo_sans_donnee")
        anomalies.append(
            Anomalie(
                "yahoo_sans_donnee",
                f"Yahoo Finance : {n} cotation(s) sans donnée ces dernières 24 h (tiret affiché)",
                "API non officielle : attendre, ou remplacer l'instrument concerné",
            )
        )
    if "awb_traduction_sans_donnee" in codes:
        anomalies.append(
            Anomalie(
                "traduction_awb",
                "Traduction AWB : aucun service gratuit n'a répondu (titres en langue d'origine)",
                "les services Google et MyMemory sont non officiels : attendre ou renseigner MYMEMORY_MAIL",
            )
        )
    if date_bourse is None:
        anomalies.append(
            Anomalie("bourse_muette", "Données de Bourse de Mizeniti illisibles",
                     "vérifier le Worker marche-lecture de Mizeniti (lecture seule)")
        )  # fmt: skip
    elif date_bourse < attendue.isoformat():
        anomalies.append(
            Anomalie(
                "bourse_perimee",
                f"Données de Bourse de Mizeniti périmées : séance du {date_bourse[8:]}/{date_bourse[5:7]} "
                f"au lieu du {attendue:%d/%m}",
                "vérifier les passages de publication de Mizeniti (pas de repli direct en place)",
            )
        )
    return anomalies
