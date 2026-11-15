"""Configuration pilotée depuis Mizeniti (contrat AC3, paragraphe 1).

La veille lit `GET <mizeniti.actualites_url>/veille/config` (jeton `VEILLE_CONFIG_TOKEN`), valide
le document par `schema/config.v1.json` et l'utilise à la place des fichiers `config/*.yaml`.
**Repli** sur les fichiers locaux, sans jamais arrêter la collecte, quand : le jeton est absent,
l'appel échoue (réseau, 404, 5xx, délai de 10 s), la version est inconnue ou la validation échoue.
Le repli est signalé par un événement de santé `config_distante_repli` (pas pour un jeton absent :
c'est l'état normal d'un essai local).

Confidentialité : ni le jeton ni le contenu reçu ne sont jamais écrits au journal. Les messages
d'échec ne contiennent que des codes, des noms de champs et des identifiants de source déjà
validés par le schéma.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema

from veille.config import (
    RACINE,
    TYPES_SOURCE,
    charger_regles_filtre,
    charger_sources,
)
from veille.http import ErreurReseau
from veille.journal import Journal

SCHEMA_CHEMIN = RACINE / "schema" / "config.v1.json"
VERSION_CONNUE = 1
DELAI_S = 10.0
ESSAIS = 2
ENTETE_AGENT = "veille-actions"
PLAGE_PAR_DEFAUT = ("22:00", "07:00")


class ConfigDistanteIndisponible(Exception):
    """Le document distant n'est pas utilisable ; le message est sûr à journaliser."""


def minutes(heure: str) -> int:
    """« 07:15 » → 435 (minutes depuis minuit)."""
    h, m = heure.split(":")
    return int(h) * 60 + int(m)


def plage_depuis(debut: str, fin: str) -> tuple[int, int]:
    return minutes(debut), minutes(fin)


@dataclass
class Configuration:
    """Ce que les points d'entrée consomment, quelle que soit l'origine."""

    origine: str  # « distante » ou « locale »
    sources: list[dict]  # toutes, actives ou non (mode test : « inconnue » ou « inactive »)
    regles_filtre: dict
    plage_silencieuse: tuple[int, int]  # minutes depuis minuit, heure de Tunis
    plafond_claude_usd: float | None = None  # None = valeur des paramètres locaux
    conservation_mois: int | None = None
    horaires: dict | None = None
    raison_repli: str | None = None
    ignorees: list[str] = field(default_factory=list)  # sources écartées (type inconnu)

    @property
    def sources_actives(self) -> list[dict]:
        return [s for s in self.sources if s["actif"]]

    def appliquer_aux_parametres(self, params: dict) -> dict:
        """Reporte le plafond Claude du document dans `params` (lu ensuite par config.plafond)."""
        if self.plafond_claude_usd is not None:
            params["claude"]["plafond_usd_mois"] = self.plafond_claude_usd
            params["claude"]["plafond_source"] = "distante"
        return params


def charger_locale(params: dict, raison_repli: str | None = None) -> Configuration:
    """Fichiers `config/*.yaml` : référence de repli et de test."""
    plage = (params.get("alertes") or {}).get("plage_silencieuse") or {}
    return Configuration(
        origine="locale",
        sources=charger_sources(),
        regles_filtre=charger_regles_filtre(),
        plage_silencieuse=plage_depuis(
            plage.get("debut", PLAGE_PAR_DEFAUT[0]), plage.get("fin", PLAGE_PAR_DEFAUT[1])
        ),
        raison_repli=raison_repli,
    )


def _schema() -> dict:
    return json.loads(Path(SCHEMA_CHEMIN).read_text(encoding="utf-8"))


def _chemin_erreur(exc: jsonschema.ValidationError) -> str:
    """Chemin du champ fautif et règle violée, jamais la valeur reçue."""
    chemin = ".".join(str(p) for p in exc.absolute_path) or "racine"
    return f"{chemin} ({exc.validator})"


def valider_document(document) -> None:
    """Lève ConfigDistanteIndisponible : version inconnue ou schéma non respecté."""
    if not isinstance(document, dict):
        raise ConfigDistanteIndisponible("document invalide : racine (type)")
    version = document.get("version")
    if version != VERSION_CONNUE or isinstance(version, bool):
        montre = version if isinstance(version, int) and not isinstance(version, bool) else "?"
        raise ConfigDistanteIndisponible(
            f"version {montre} inconnue (cette veille lit la version {VERSION_CONNUE})"
        )
    try:
        jsonschema.validate(document, _schema())
    except jsonschema.ValidationError as exc:
        raise ConfigDistanteIndisponible(f"document invalide : {_chemin_erreur(exc)}") from exc
    ids = [s["id"] for s in document["sources"]]
    if len(set(ids)) != len(ids):
        raise ConfigDistanteIndisponible("document invalide : sources.id en double")


def _telecharger(client, base: str, token: str) -> dict:
    url = base.rstrip("/") + "/veille/config"
    try:
        reponse = client.get(
            url,
            timeout=DELAI_S,
            essais=ESSAIS,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "User-Agent": ENTETE_AGENT,
            },
        )
    except ErreurReseau as exc:
        raise ConfigDistanteIndisponible("serveur injoignable (réseau ou délai de 10 s)") from exc
    code = reponse.status_code
    if code == 404:
        raise ConfigDistanteIndisponible(
            "HTTP 404 : route absente (jeton VEILLE_CONFIG_TOKEN non posé côté Worker ?)"
        )
    if code in (401, 403):
        raise ConfigDistanteIndisponible(f"HTTP {code} : jeton refusé par le Worker")
    if code != 200:
        raise ConfigDistanteIndisponible(f"HTTP {code}")
    try:
        return reponse.json()
    except ValueError as exc:
        raise ConfigDistanteIndisponible("réponse illisible (JSON invalide)") from exc


def _source_locale(s: dict) -> dict:
    """Entrée de source au format de `config/sources.yaml`."""
    out = {
        k: s[k]
        for k in ("id", "nom", "url", "type", "chapitre", "langue", "alerte", "payant", "actif")
    }
    if "filtre" in s:
        out["filtre"] = s["filtre"]
    if s["type"] == "html-generique" and s.get("selecteur"):
        out["selecteur"] = s["selecteur"]  # réservé à html-generique (contrat)
    return out


def _depuis_document(document: dict, locale: Configuration, journal: Journal) -> Configuration:
    sources, ignorees = [], []
    for s in document["sources"]:
        if s["type"] not in TYPES_SOURCE:
            ignorees.append(s["id"])
            journal.avertir(
                "config_source_ignoree",
                f"source {s['id']} ignorée : type non pris en charge par cette veille",
                source=s["id"],
            )
            continue
        sources.append(_source_locale(s))
    regles = {
        **locale.regles_filtre,
        "mots_exclus": {
            groupe: list(mots)
            for groupe, mots in document["ligne_editoriale"]["mots_exclus"].items()
        },
    }
    plage = document["horaires"]["plage_silencieuse"]
    return Configuration(
        origine="distante",
        sources=sources,
        regles_filtre=regles,
        plage_silencieuse=plage_depuis(plage["debut"], plage["fin"]),
        plafond_claude_usd=float(document["parametres"]["plafond_claude_usd_mois"]),
        conservation_mois=int(document["parametres"]["conservation_mois"]),
        horaires=document["horaires"],
        ignorees=ignorees,
    )


def charger_configuration(client, params: dict, journal: Journal, *, token: str | None = None):
    """Configuration effective : distante si possible, sinon fichiers locaux. Ne lève jamais pour
    une raison tenant au document distant ou au réseau (une erreur des fichiers locaux, elle,
    reste fatale : il n'y aurait plus de référence)."""
    if token is None:
        token = os.environ.get("VEILLE_CONFIG_TOKEN") or None
    locale = charger_locale(params)
    if not token:
        journal.info("config_locale", "VEILLE_CONFIG_TOKEN absent : fichiers locaux config/*.yaml")
        return locale
    base = (params.get("mizeniti") or {}).get("actualites_url")
    try:
        if not base:
            raise ConfigDistanteIndisponible("mizeniti.actualites_url absent des paramètres")
        document = _telecharger(client, base, token)
        valider_document(document)
        configuration = _depuis_document(document, locale, journal)
    except ConfigDistanteIndisponible as exc:
        raison = journal.masquer(str(exc))
        journal.avertir(
            "config_distante_repli", f"configuration locale utilisée : {raison}", raison=raison
        )
        locale.raison_repli = raison
        return locale
    except Exception as exc:  # noqa: BLE001 - jamais d'arrêt de la collecte pour la config distante
        raison = f"erreur inattendue ({type(exc).__name__})"
        journal.avertir(
            "config_distante_repli", f"configuration locale utilisée : {raison}", raison=raison
        )
        locale.raison_repli = raison
        return locale
    actives = len(configuration.sources_actives)
    journal.info(
        "config_distante",
        f"configuration distante utilisée : {actives} source(s) active(s)",
        sources=len(configuration.sources),
        ignorees=len(configuration.ignorees),
    )
    return configuration
