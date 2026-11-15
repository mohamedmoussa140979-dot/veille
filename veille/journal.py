"""Journal : sortie console + événements structurés, avec masquage des secrets.

Tout texte écrit passe par `masquer` : une valeur de secret enregistrée ne sort jamais,
même si une bibliothèque la recopie dans un message d'erreur (URL Telegram, par exemple).
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from datetime import datetime
from typing import Any

from veille import temps

# Variables d'environnement dont la valeur est un secret (spec § 11).
SECRETS_ENV = (
    "GEMINI_API_KEY",
    "ANTHROPIC_API_KEY",
    "TG_TOKEN_VEILLE",
    "TG_CHAT_ID",
    "MYMEMORY_MAIL",
    "MIZENITI_INGEST_TOKEN",
    "VEILLE_CONFIG_TOKEN",
    "GITHUB_TOKEN",
)
LONGUEUR_MIN_SECRET = 4


class Journal:
    def __init__(
        self,
        sortie: Callable[[str], None] = print,
        horloge: Callable[[], datetime] = temps.maintenant,
    ):
        self._sortie = sortie
        self._horloge = horloge
        self._secrets: set[str] = set()
        self.evenements: list[dict[str, Any]] = []

    @classmethod
    def depuis_env(cls, **kw) -> Journal:
        j = cls(**kw)
        for nom in SECRETS_ENV:
            j.enregistrer_secret(os.environ.get(nom, ""))
        return j

    def enregistrer_secret(self, valeur: str | None) -> None:
        if valeur and len(valeur) >= LONGUEUR_MIN_SECRET:
            self._secrets.add(valeur)

    def masquer(self, texte: str) -> str:
        for secret in sorted(self._secrets, key=len, reverse=True):
            texte = texte.replace(secret, "***")
        return texte

    def log(self, niveau: str, code: str, message: str = "", **contexte: Any) -> dict[str, Any]:
        evenement = {
            "t": temps.en_tunis(self._horloge()).isoformat(),
            "niveau": niveau,
            "code": code,
            "message": self.masquer(message),
            "ctx": {k: self.masquer(str(v)) for k, v in contexte.items()},
        }
        self.evenements.append(evenement)
        suite = f" {evenement['ctx']}" if evenement["ctx"] else ""
        self._sortie(f"[{niveau}] {code} {evenement['message']}{suite}".rstrip())
        return evenement

    def info(self, code: str, message: str = "", **contexte: Any):
        return self.log("info", code, message, **contexte)

    def avertir(self, code: str, message: str = "", **contexte: Any):
        return self.log("avertissement", code, message, **contexte)

    def erreur(self, code: str, message: str = "", **contexte: Any):
        return self.log("erreur", code, message, **contexte)

    def avec_niveau(self, niveau: str) -> list[dict[str, Any]]:
        return [e for e in self.evenements if e["niveau"] == niveau]

    def vers_jsonl(self) -> str:
        return "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in self.evenements)
