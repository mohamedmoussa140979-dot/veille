"""Veille AWB : `python -m veille.awb [--a-blanc]`, message 🏦 (spec § 5 : 08:30 et 18:30)."""

from __future__ import annotations

import json
import os
import sys

from veille import temps
from veille.awb import config as cfg_awb
from veille.awb.collecte import collecter, selectionner
from veille.awb.message import construire_message
from veille.awb.traduction import Traducteur
from veille.collecte.article import nettoyer_url
from veille.collecte.liens import est_google_news, resoudre_google_news
from veille.config import charger_parametres
from veille.etat import EtatGit, EtatLocal
from veille.http import Client
from veille.journal import Journal
from veille.telegram import envoyer

MAX_VUS = 8000


def resoudre_et_nettoyer(
    retenus: list[dict], client, journal, cache: dict, jour: str
) -> list[dict]:
    """URL réelle de chaque article (jamais de lien Google News) ; un échec écarte l'article."""
    gardes = []
    for it in retenus:
        if est_google_news(it["lien"]):
            ident = it["lien"].split("/articles/")[-1].split("?")[0]
            reel = (cache.get(ident) or [""])[0] or resoudre_google_news(
                client, it["lien"], journal
            )
            if not reel:
                continue
            cache[ident] = [reel, jour]
            it["lien"] = reel
        it["lien"] = nettoyer_url(it["lien"])
        gardes.append(it)
    return gardes


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    a_blanc = "--a-blanc" in argv
    journal = Journal.depuis_env()
    params = charger_parametres()
    client = Client(journal=journal, essais=params["http"]["essais"], delai_hote=0.5)
    client_gnews = Client(journal=journal, essais=2, delai_hote=0.4)
    # GDELT : une requête toutes les 5 s au plus (constat : 429 à 5,2 s)
    client_gdelt = Client(journal=journal, essais=1, delai_hote=8.0)
    etat = (
        EtatLocal("_etat_local")
        if a_blanc
        else EtatGit.depuis_environnement(journal=journal).ouvrir()
    )
    token = None if a_blanc else os.environ.get("TG_TOKEN_VEILLE")
    chat_id = None if a_blanc else os.environ.get("TG_CHAT_ID")

    cfg = cfg_awb.charger()
    maintenant = temps.maintenant()
    ts = int(maintenant.timestamp())
    jour = temps.en_tunis(maintenant).date().isoformat()
    vus: dict[str, int] = etat.lire_json("state/awb_vus.json", {})
    cache_gn: dict = etat.lire_json("state/gnews.json", {})

    items, erreurs = collecter(cfg, client_gnews, client_gdelt, client, maintenant, journal)
    retenus, uniques = selectionner(cfg, items, vus, ts)
    retenus = resoudre_et_nettoyer(retenus[: cfg["max_envois"]], client, journal, cache_gn, jour)
    print(f"{len(items)} articles pertinents, {len(uniques)} nouveaux, {len(retenus)} à envoyer")
    print(f"flux en erreur : {erreurs}")
    if sum(erreurs.values()):
        journal.avertir("awb_flux_en_erreur_resume", json.dumps(erreurs))

    traducteur = Traducteur(client, journal)
    envoye = False
    if retenus:
        corps = construire_message(retenus, traducteur)
        print(corps.replace("<b>", "").replace("</b>", "")[:1500])
        if token and chat_id:
            try:
                envoyer("awb", corps, token=token, chat_id=chat_id, client=client, journal=journal)
                envoye = True
            except Exception as exc:  # noqa: BLE001 - non marqués vus : réessai au passage suivant
                journal.erreur("awb_telegram_echec", journal.masquer(str(exc))[:200])
    if traducteur.demandees and not traducteur.reussies:
        journal.erreur(
            "awb_traduction_sans_donnee", f"{traducteur.demandees} traduction(s) sans résultat"
        )

    def ecrire(tx) -> None:
        frais = json.loads(tx.lire("state/awb_vus.json", "{}") or "{}")
        for it in uniques.values():
            frais.setdefault(it["cle"], ts)
        if envoye:
            for it in retenus:
                frais[it["cle"]] = ts
                if it.get("evenement"):
                    frais[it["evenement"]] = ts
        if len(frais) > MAX_VUS:
            frais = dict(sorted(frais.items(), key=lambda kv: kv[1])[-MAX_VUS:])
        tx.ecrire("state/awb_vus.json", json.dumps(frais, ensure_ascii=False) + "\n")
        gn = {**json.loads(tx.lire("state/gnews.json", "{}") or "{}"), **cache_gn}
        tx.ecrire("state/gnews.json", json.dumps(gn, ensure_ascii=False, sort_keys=True) + "\n")
        stats = {
            "dernier_passage": maintenant.isoformat(),
            "articles": len(items),
            "envoyes": len(retenus) if envoye else 0,
            "traductions_demandees": traducteur.demandees,
            "traductions_reussies": traducteur.reussies,
            "flux_en_erreur": erreurs,
        }
        tx.ecrire("state/awb.json", json.dumps(stats, ensure_ascii=False) + "\n")

    etat.transaction("data: veille AWB", ecrire)
    if not a_blanc:
        utiles = [e for e in journal.evenements if e["niveau"] != "info"]
        if utiles:
            etat.ajouter_lignes(
                f"sante/{temps.mois()}.jsonl",
                [json.dumps(e, ensure_ascii=False) for e in utiles],
                "data: journal AWB",
            )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
