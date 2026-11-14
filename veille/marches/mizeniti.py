"""Données de Bourse et taux BCT déjà publiés par Mizeniti (Worker `marche-lecture`, spec § 6.4).

Lecture HTTP seule, anonyme : le dépôt `veille` ne modifie jamais `marche-jobs` ni le Worker (V42).
Aucun rediffuseur, aucune donnée recalculée quand la Bourse la publie : seules les variations que
Mizeniti ne sert pas (indices à fréquence mensuelle) sont calculées, et marquées comme telles.
"""

from __future__ import annotations

from veille.http import ErreurReseau

BVMT_EMETTEURS = "https://tunis-stockexchange.com/emetteurs"  # fiche par valeur : introuvable (V3)
BCT_COURS = "https://www.bct.gov.tn/bct/siteprod/cours.jsp"
BCT_TMM = "https://www.bct.gov.tn/bct/siteprod/tableau_statistique_a.jsp?params=PL203105"
INDICES_RETENUS = {"TUNINDEX": "tunindex", "TUNINDEX20": "tunindex20", "8300": "banques"}
SOURCE = "Bourse de Tunis"


def _json(client, base: str, chemin: str, journal=None):
    """JSON de la route, ou None si Mizeniti ne répond pas correctement (tiret affiché)."""
    try:
        r = client.get(base.rstrip("/") + chemin, essais=2)
        if r.status_code != 200:
            raise ErreurReseau(f"HTTP {r.status_code}")
        return r.json()
    except (ErreurReseau, ValueError) as exc:
        if journal:
            journal.avertir("mizeniti_muet", str(exc)[:160], route=chemin)
        return None


def _variation(valeur: float | None, precedente: float | None) -> float | None:
    if not valeur or not precedente:
        return None
    return round((valeur / precedente - 1) * 100, 2)


def lire_bourse(indices: dict | None, index: dict | None, volumes: dict | None) -> dict | None:
    """Point Bourse : indices, trois plus fortes hausses et baisses, capitaux. None si rien."""
    if not indices or not indices.get("indices"):
        return None
    par_code = {i["code"]: i for i in indices["indices"]}
    lignes, provisoire = [], False
    for code, cle in INDICES_RETENUS.items():
        i = par_code.get(code)
        if not i:
            continue
        publiee = i.get("variation_jour")
        variation = publiee if publiee is not None else _variation(i["valeur"], i.get("precedente"))
        provisoire = provisoire or i.get("statut") == "P"
        lignes.append(
            {
                "cle": cle,
                "libelle": i["libelle"],
                "valeur": round(i["valeur"] / 100, 2),
                "variation_pct": variation,
                "variation_calculee": publiee is None and variation is not None,
                "variation_annee_pct": i.get("variation_annee"),
                "au": i["date"],
                "source_url": BVMT_EMETTEURS,
            }
        )
    if not lignes:
        return None
    seance = next((ligne["au"] for ligne in lignes if ligne["cle"] == "tunindex"), lignes[0]["au"])

    valeurs = []
    for v in (index or {}).get("valeurs", []):
        # valeurs non cotées du jour (volume nul) ignorées ; seulement la séance en cours
        if not v.get("v") or v.get("d") != seance or not v.get("p") or not v.get("k"):
            continue
        provisoire = provisoire or v.get("s") == "P"
        valeurs.append(
            {
                "cle": v["m"].lower(),
                "libelle": v["l"],
                "valeur": round(v["k"] / 1000, 3),
                "variation_pct": _variation(v["k"], v["p"]),
                "au": v["d"],
                "source_url": BVMT_EMETTEURS,
            }
        )
    hausses = sorted(
        (v for v in valeurs if v["variation_pct"] > 0), key=lambda v: -v["variation_pct"]
    )
    baisses = sorted(
        (v for v in valeurs if v["variation_pct"] < 0), key=lambda v: v["variation_pct"]
    )

    capitaux = None
    for s in (volumes or {}).get("seances", []):
        if s.get("d") == seance and s.get("capitaux"):
            capitaux = {
                "capitaux_mtnd": round(s["capitaux"] / 1_000_000_000, 2),
                "titres": s.get("titres"),
                "transactions": s.get("transactions"),
                "estimes": bool(s.get("capitaux_estimes")),
            }
    return {
        "seance": seance,
        "provisoire": provisoire,
        "source": SOURCE,
        "indices": lignes,
        "hausses": hausses[:3],
        "baisses": baisses[:3],
        "capitaux": capitaux,
        "nb_cotees": len(valeurs),
    }


def lire_taux(tmm: dict | None, tre: dict | None, change: dict | None) -> dict:
    """TMM, TRE et cours moyens BCT (EUR/TND, USD/TND) ; chaque absence reste None."""
    sortie: dict = {"tmm": None, "tre": None, "eur_tnd": None, "usd_tnd": None}
    for cle, d, url in (("tmm", tmm, BCT_TMM), ("tre", tre, None)):
        if d and d.get("derniere"):
            sortie[cle] = {
                "valeur": d["derniere"]["valeur"],
                "periode": d["derniere"]["periode"],
                "source_url": url or d.get("url_source"),
            }
    for dev in (change or {}).get("devises", []):
        if dev["code"] in ("EUR", "USD"):
            sortie[f"{dev['code'].lower()}_tnd"] = {
                "valeur": dev["cours"],
                "variation_pct": dev.get("variation_pct"),
                "au": (change or {}).get("jour"),
                "source_url": BCT_COURS,
            }
    return sortie


def charger(client, base: str, journal=None) -> tuple[dict | None, dict]:
    """(point Bourse, taux) lus chez Mizeniti ; None / valeurs vides si le Worker est muet."""
    indices = _json(client, base, "/marche/bourse/indices.json", journal)
    index = _json(client, base, "/marche/bourse/index.json", journal)
    volumes = _json(client, base, "/marche/bourse/volumes.json", journal)
    tmm = _json(client, base, "/marche/taux/tmm.json", journal)
    tre = _json(client, base, "/marche/taux/tre.json", journal)
    change = _json(client, base, "/marche/taux/change.json", journal)
    return lire_bourse(indices, index, volumes), lire_taux(tmm, tre, change)
