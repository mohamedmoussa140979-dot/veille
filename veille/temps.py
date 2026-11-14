"""Heure de Tunis : UTC+1 toute l'année (pas d'heure d'été, spec § 5)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

TUNIS = timezone(timedelta(hours=1), "Africa/Tunis")


def maintenant() -> datetime:
    return datetime.now(UTC)


def en_tunis(instant: datetime) -> datetime:
    return instant.astimezone(TUNIS)


def mois(instant: datetime | None = None) -> str:
    """Mois civil à Tunis, au format AAAA-MM (clé du compteur Claude)."""
    return en_tunis(instant or maintenant()).strftime("%Y-%m")
