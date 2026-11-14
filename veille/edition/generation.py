"""Produit un fichier d'édition valide à partir des articles collectés (deux appels IA au plus)."""

from __future__ import annotations

from datetime import datetime

from veille import temps
from veille.edition import prompts
from veille.edition.modele import (
    CHAPITRES,
    CHIFFRES_VIDES,
    MAX_ESSENTIEL,
    MAX_SUJETS,
    TITRES,
    valider_edition,
)
from veille.journal import Journal


class AucuneActualite(Exception):
    """Rien de retenu dans la fenêtre : pas d'édition (jamais d'édition vide)."""


def _classer(ia, articles: list[dict], journal: Journal) -> tuple[list[dict], str]:
    """Appel 1. Renvoie les sujets (chapitre, rubrique, articles) classés par importance."""
    par_id = {a["id"]: a for a in articles}
    res = ia.generer_json(
        prompts.prompt_classement(articles),
        prompts.SCHEMA_CLASSEMENT,
        systeme=prompts.LIGNE_EDITORIALE,
        normaliser=prompts.normaliser_classement,
    )
    inconnus = 0
    sujets: dict[tuple[str, str], dict] = {}
    for c in res.donnees["articles"]:
        if c["id"] not in par_id:
            inconnus += 1  # identifiant inventé : ignoré
            continue
        if c["chapitre"] == "hors-ligne":
            continue
        cle = (c["chapitre"], c.get("sujet") or c["id"])
        s = sujets.setdefault(
            cle,
            {"chapitre": c["chapitre"], "rubrique": None, "articles": [], "importance": 1},
        )
        if c["id"] not in s["articles"]:
            s["articles"].append(c["id"])
        s["importance"] = max(s["importance"], c.get("importance") or 1)
        if c["chapitre"] == "eco-tunisie" and not s["rubrique"]:
            s["rubrique"] = c.get("rubrique") or "presse"
    if inconnus:
        journal.avertir("edition_ids_inconnus", f"{inconnus} identifiant(s) inconnus ignorés")
    retenus: list[dict] = []
    for cle, _ in CHAPITRES:
        du_chapitre = [s for s in sujets.values() if s["chapitre"] == cle]
        du_chapitre.sort(key=lambda s: (-s["importance"], -len(s["articles"])))
        retenus += du_chapitre[:MAX_SUJETS]
    for i, s in enumerate(retenus, 1):
        s["cle"] = f"s{i}"
    return retenus, res.modele


def _articles_tries(ids: list[str], par_id: dict[str, dict]) -> list[str]:
    return sorted(ids, key=lambda i: par_id[i].get("publie_le") or "", reverse=True)


def produire_edition(
    *,
    ia,
    articles: list[dict],
    type_enregistre: str,
    ident: str,
    maintenant: datetime,
    journal: Journal,
    marches: dict | None = None,
) -> dict:
    """Édition conforme au schéma v1 (lève `AucuneActualite` ou `EditionInvalide`).

    `marches` (lot V3) : {"chiffres": [...], "tableaux": {chapitre: tableau}} ; sans lui, les
    quatre chiffres valent `null` et les chapitres n'ont pas de tableau.
    """
    if not articles:
        raise AucuneActualite("aucun article dans la fenêtre")
    par_id = {a["id"]: a for a in articles}
    sujets, modele = _classer(ia, articles, journal)
    if not sujets:
        raise AucuneActualite("aucun article retenu par le classement")

    cites = [i for s in sujets for i in s["articles"]]
    a_traduire = [i for i in cites if par_id[i]["langue"] != "fr"]
    res = ia.generer_json(
        prompts.prompt_redaction(sujets, par_id, a_traduire),
        prompts.SCHEMA_REDACTION,
        systeme=prompts.LIGNE_EDITORIALE,
    )
    modele = res.modele
    redige = {s["cle"]: s for s in res.donnees["sujets"]}
    titres_fr = {
        t["id"]: t["titre"].strip() for t in res.donnees.get("titres_fr", []) if t["id"] in par_id
    }

    chapitres = []
    for cle, titre in CHAPITRES:
        du_chapitre = []
        for s in (x for x in sujets if x["chapitre"] == cle):
            r = redige.get(s["cle"])
            premier = par_id[s["articles"][0]]
            ligne = {
                "titre": (r or {}).get("titre") or titres_fr.get(premier["id"]) or premier["titre"],
                "texte": (r or {}).get("texte") or premier.get("resume") or premier["titre"],
                "articles": _articles_tries(s["articles"], par_id),
            }
            if cle == "eco-tunisie":
                ligne["rubrique"] = s["rubrique"]
                ligne["impact_menage"] = (r or {}).get("impact_menage") or None
            du_chapitre.append(ligne)
        tableau = ((marches or {}).get("tableaux") or {}).get(cle)
        if du_chapitre or tableau:  # un chapitre sans sujet garde son tableau fixe
            chapitres.append(
                {"cle": cle, "titre": titre, "tableau": tableau, "sujets": du_chapitre}
            )

    par_cle = {s["cle"]: s for s in sujets}
    essentiel = []
    for point in res.donnees["essentiel"][:MAX_ESSENTIEL]:
        ids = []
        for k in point["sujets"]:
            ids += par_cle[k]["articles"] if k in par_cle else []
        ids = list(dict.fromkeys(ids))
        if ids and point["texte"].strip():
            essentiel.append(
                {"texte": point["texte"].strip(), "articles": _articles_tries(ids, par_id)}
            )
    if not essentiel:  # « Toujours présent » : repli sur les premiers sujets
        journal.avertir("edition_essentiel_repli", "essentiel vide, repli sur les premiers sujets")
        for c in chapitres:
            essentiel += [{"texte": s["titre"], "articles": s["articles"][:1]} for s in c["sujets"]]
        essentiel = essentiel[:3]

    utilises = {i for c in chapitres for s in c["sujets"] for i in s["articles"]}
    utilises |= {i for p in essentiel for i in p["articles"]}
    carte = {}
    for i in sorted(utilises):
        a = par_id[i]
        entree = {
            "titre": titres_fr.get(i) or a["titre"],
            "source": a["source"],
            "url": a["url"],
            "url_traduite": a.get("url_traduite"),
            "publie_le": a.get("publie_le"),
            "langue": a["langue"],
            "payant": bool(a["payant"]),
        }
        if a["langue"] != "fr":
            entree["titre_origine"] = a.get("titre_origine") or a["titre"]
        carte[i] = entree

    edition = {
        "version": 1,
        "id": ident,
        "date": ident[:10],
        "edition": type_enregistre,
        "genere_le": temps.en_tunis(maintenant).replace(microsecond=0).isoformat(),
        "modele": modele,
        "chiffres": (marches or {}).get("chiffres")
        or [
            {**c, "valeur": None, "variation_pct": None, "source_url": None, "au": None}
            for c in CHIFFRES_VIDES
        ],
        "essentiel": essentiel,
        "chapitres": chapitres,
        "articles": carte,
    }
    valider_edition(edition)
    journal.info("edition_produite", ident, sujets=len(sujets), articles=len(carte), modele=modele)
    return edition


__all__ = ["AucuneActualite", "produire_edition", "TITRES"]
