"""Cotations internationales (Yahoo Finance, API non officielle ; repli : tiret, spec § 6.1)."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import quote

from veille import temps
from veille.http import ErreurReseau

API = "https://query1.finance.yahoo.com/v8/finance/chart/"
PAGE = "https://finance.yahoo.com/quote/"

# (clé, libellé, symbole Yahoo, unité). Le MASI n'a pas de symbole Yahoo : tiret (constat V3).
INSTRUMENTS = [
    ("brent", "Brent", "BZ=F", "USD le baril"),
    ("gaz", "Gaz naturel", "NG=F", "USD par MMBtu"),
    ("or", "Or", "GC=F", "USD l'once"),
    ("ble", "Blé", "ZW=F", "cents le boisseau"),
    ("sp500", "S&P 500", "^GSPC", "points"),
    ("eurostoxx50", "Euro Stoxx 50", "^STOXX50E", "points"),
    ("cac40", "CAC 40", "^FCHI", "points"),
    ("masi", "MASI", None, "points"),
    ("eurusd", "EUR/USD", "EURUSD=X", ""),
]


def lire_chart(donnees: dict) -> dict | None:
    """Prix, clôture précédente, variation du jour et date, depuis une réponse `chart`."""
    try:
        meta = donnees["chart"]["result"][0]["meta"]
        prix = meta["regularMarketPrice"]
    except (KeyError, IndexError, TypeError):
        return None
    precedent = meta.get("chartPreviousClose") or meta.get("previousClose")
    instant = meta.get("regularMarketTime")
    return {
        "valeur": prix,
        "precedent": precedent,
        "variation_pct": round((prix / precedent - 1) * 100, 2) if precedent else None,
        "devise": meta.get("currency"),
        "au": temps.en_tunis(datetime.fromtimestamp(instant, UTC)).date().isoformat()
        if instant
        else None,
    }


def lire_internationaux(client, journal=None) -> dict[str, dict | None]:
    """Cotations de INSTRUMENTS ; un instrument en panne vaut None (jamais un zéro)."""
    sortie: dict[str, dict | None] = {}
    for cle, libelle, symbole, unite in INSTRUMENTS:
        sortie[cle] = None
        if not symbole:
            continue
        try:
            r = client.get(API + quote(symbole, safe="^="), essais=2)
            cotation = lire_chart(r.json()) if r.status_code == 200 else None
        except (ErreurReseau, ValueError) as exc:
            cotation = None
            if journal:
                journal.avertir("yahoo_echec", str(exc)[:160], instrument=cle)
        if cotation:
            cotation.update(libelle=libelle, unite=unite, source_url=PAGE + quote(symbole, safe=""))
            sortie[cle] = cotation
        elif journal and symbole:
            journal.avertir("yahoo_sans_donnee", libelle, instrument=cle)
    return sortie
