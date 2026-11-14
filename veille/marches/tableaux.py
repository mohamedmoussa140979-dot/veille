"""Tableaux fixes des chapitres 3 et 4 et quatre chiffres de l'édition (spec § 4, § 8.2)."""

from __future__ import annotations

from veille.marches.mizeniti import BCT_COURS, SOURCE
from veille.marches.yahoo import INSTRUMENTS


def tableau_bourse(bourse: dict | None) -> dict | None:
    """Chapitre 3 : TUNINDEX, indice Banques, trois plus fortes hausses et baisses.

    None quand Mizeniti est muet : le chapitre n'a alors pas de tableau (jamais de chiffre inventé).
    """
    if not bourse:
        return None
    return {
        "titre": "Bourse de Tunis",
        "source": SOURCE,
        "seance": bourse["seance"],
        "provisoire": bourse["provisoire"],
        "lignes": [
            {
                k: ligne.get(k)
                for k in (
                    "cle",
                    "libelle",
                    "valeur",
                    "variation_pct",
                    "variation_annee_pct",
                    "au",
                    "source_url",
                )
            }
            for ligne in bourse["indices"]
            if ligne["cle"] in ("tunindex", "banques")
        ],
        "hausses": bourse["hausses"],
        "baisses": bourse["baisses"],
    }


def tableau_international(yahoo: dict[str, dict | None], taux: dict) -> dict:
    """Chapitre 4 : Brent, gaz, or, blé ; S&P 500, Euro Stoxx 50, CAC 40, MASI ; EUR/USD ;
    cours moyens BCT EUR/TND et USD/TND. Une donnée absente garde sa ligne, avec `valeur: null`."""
    lignes = []
    for cle, libelle, _symbole, unite in INSTRUMENTS:
        c = yahoo.get(cle)
        lignes.append(
            {
                "cle": cle,
                "libelle": libelle,
                "valeur": c["valeur"] if c else None,
                "unite": unite,
                "variation_pct": c["variation_pct"] if c else None,
                "au": c["au"] if c else None,
                "source_url": c["source_url"] if c else None,
            }
        )
    for cle, libelle in (("eur_tnd", "EUR/TND (BCT)"), ("usd_tnd", "USD/TND (BCT)")):
        t = taux.get(cle)
        lignes.append(
            {
                "cle": cle,
                "libelle": libelle,
                "valeur": t["valeur"] if t else None,
                "unite": "dinars",
                "variation_pct": t.get("variation_pct") if t else None,
                "au": t.get("au") if t else None,
                "source_url": BCT_COURS if t else None,
            }
        )
    return {"titre": "Marchés internationaux", "lignes": lignes}


def chiffres(bourse: dict | None, yahoo: dict[str, dict | None], taux: dict) -> list[dict]:
    """Les quatre chiffres de l'en-tête Mizeniti : TUNINDEX, EUR/TND (BCT), Brent, TMM."""
    tunindex = next((i for i in (bourse or {}).get("indices", []) if i["cle"] == "tunindex"), None)
    brent, eur, tmm = yahoo.get("brent"), taux.get("eur_tnd"), taux.get("tmm")
    return [
        {"cle": "tunindex", "libelle": "TUNINDEX",
         "valeur": tunindex["valeur"] if tunindex else None,
         "variation_pct": tunindex["variation_pct"] if tunindex else None,
         "source_url": tunindex["source_url"] if tunindex else None,
         "au": tunindex["au"] if tunindex else None},
        {"cle": "eur_tnd_bct", "libelle": "EUR/TND (BCT)",
         "valeur": eur["valeur"] if eur else None,
         "variation_pct": eur.get("variation_pct") if eur else None,
         "source_url": BCT_COURS if eur else None,
         "au": eur.get("au") if eur else None},
        {"cle": "brent", "libelle": "Brent",
         "valeur": brent["valeur"] if brent else None,
         "variation_pct": brent["variation_pct"] if brent else None,
         "source_url": brent["source_url"] if brent else None,
         "au": brent["au"] if brent else None},
        {"cle": "tmm", "libelle": "TMM",
         "valeur": tmm["valeur"] if tmm else None,
         "variation_pct": None,
         "source_url": tmm["source_url"] if tmm else None,
         "au": (tmm["periode"] + "-01") if tmm else None},
    ]  # fmt: skip
