"""Mise en forme des nombres à la française (milliers séparés, virgule décimale, signe)."""

from __future__ import annotations

NBSP = " "  # espace fine insécable


def nombre(x: float | None, decimales: int = 2) -> str:
    if x is None:
        return "—"
    s = f"{x:,.{decimales}f}".replace(",", NBSP).replace(".", ",")
    return s


def signe(x: float | None, decimales: int = 2, suffixe: str = " %") -> str:
    """Variation signée : « +0,79 % », « −1,20 % » (vrai signe moins), « — » si absente."""
    if x is None:
        return "—"
    s = f"{abs(x):.{decimales}f}".replace(".", ",")
    prefixe = "+" if x > 0 else ("−" if x < 0 else "")
    return f"{prefixe}{s}{suffixe}"


def date_courte(iso: str | None) -> str:
    """2026-11-13 -> 13/11/2026."""
    if not iso:
        return "—"
    a, m, j = iso[:10].split("-")
    return f"{j}/{m}/{a}"
