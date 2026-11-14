"""Un passage de collecte : sources → liens → filtre → déduplication → état → alertes."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from veille import temps
from veille.collecte import alertes, dedup
from veille.collecte.article import Article, nettoyer_url
from veille.collecte.filtre import Filtre
from veille.collecte.lecteurs import ErreurLecture, lire
from veille.collecte.liens import (
    detecter_langue,
    est_google_news,
    lien_traduit,
    resoudre_google_news,
)
from veille.http import ErreurReseau
from veille.journal import Journal
from veille.telegram import envoyer as envoyer_telegram

AGE_MAX = timedelta(days=14)  # on n'accueille pas d'article plus ancien
BASELINE_FENETRE = timedelta(hours=24)  # au premier passage d'une source : seulement le très récent
VUS_JOURS = 60
TITRES_JOURS = 3
PURGE_ARTICLES_JOURS = 90
MAX_RESOLUTIONS = 80


@dataclass
class Rapport:
    sources_ok: int = 0
    sources_en_erreur: dict[str, str] = field(default_factory=dict)
    lus: int = 0
    rejetes: dict[str, int] = field(default_factory=dict)
    nouveaux: int = 0
    alertes_envoyees: int = 0
    alertes_en_attente: int = 0
    resolutions: int = 0
    resolutions_echec: int = 0


def _jour(instant: datetime) -> str:
    return temps.en_tunis(instant).date().isoformat()


def _ident_gnews(url: str) -> str | None:
    m = re.search(r"/articles/([^/?#]+)", url)
    return m.group(1) if m else None


def _recolter(sources, client, journal, maintenant, stats, rapport) -> list[Article]:
    """Lit chaque source ; une source en panne n'arrête jamais les autres."""
    articles: list[Article] = []
    for s in sources:
        st = stats.setdefault(s["id"], {})
        st["dernier_essai"] = maintenant.isoformat()
        try:
            r = client.get(s["url"], ssl_repli=True)
            if r.status_code != 200:
                raise ErreurLecture(f"HTTP {r.status_code}")
            lus = lire(s, r.content)
        except (ErreurReseau, ErreurLecture, ValueError) as exc:
            st["erreurs_consecutives"] = st.get("erreurs_consecutives", 0) + 1
            st["derniere_erreur"] = journal.masquer(str(exc))[:200]
            rapport.sources_en_erreur[s["id"]] = st["derniere_erreur"]
            journal.avertir("source_en_erreur", st["derniere_erreur"], source=s["id"])
            continue
        st["erreurs_consecutives"] = 0
        st.pop("derniere_erreur", None)
        st["dernier_ok"] = maintenant.isoformat()
        st["n_dernier"] = len(lus)
        rapport.sources_ok += 1
        articles += lus
    rapport.lus = len(articles)
    return articles


def _resoudre_liens(articles, client, journal, cache, maintenant, rapport) -> list[Article]:
    """Remplace les liens Google News par l'URL réelle ; un lien non résolu écarte l'article."""
    gardes, restantes = [], MAX_RESOLUTIONS
    for a in articles:
        if not est_google_news(a.url):
            gardes.append(a)
            continue
        ident = _ident_gnews(a.url)
        if ident in cache:
            a.url = cache[ident][0]
            gardes.append(a)
        elif ident and restantes > 0:
            restantes -= 1
            reel = resoudre_google_news(client, a.url, journal)
            if reel:
                rapport.resolutions += 1
                cache[ident] = [reel, _jour(maintenant)]
                a.url = reel
                gardes.append(a)
            else:
                rapport.resolutions_echec += 1
    return gardes


def collecter(
    *,
    sources: list[dict],
    client,
    journal: Journal,
    etat,
    filtre: Filtre,
    maintenant: datetime,
    token: str | None = None,
    chat_id: str | None = None,
    envoyer=envoyer_telegram,
) -> Rapport:
    rapport = Rapport()
    etat.synchroniser()
    vus: dict[str, str] = etat.lire_json("state/vus.json", {})
    stats: dict[str, dict] = etat.lire_json("state/sources.json", {})
    cache_gn: dict[str, list[str]] = etat.lire_json("state/gnews.json", {})
    titres: list[dict] = etat.lire_json("state/titres.json", [])
    # « Premier passage » : tant qu'aucune lecture de la source n'a réussi (même après un échec).
    premieres = {s["id"] for s in sources if "premier_passage" not in stats.get(s["id"], {})}
    par_id = {s["id"]: s for s in sources}

    articles = _recolter(sources, client, journal, maintenant, stats, rapport)
    articles = [
        a
        for a in articles
        if not a.publie_le or maintenant - datetime.fromisoformat(a.publie_le) <= AGE_MAX
    ]
    articles = _resoudre_liens(articles, client, journal, cache_gn, maintenant, rapport)

    nouveaux: list[Article] = []
    ids_du_passage: set[str] = set()
    for a in articles:
        a.url = nettoyer_url(a.url)
        if a.id in vus or a.id in ids_du_passage:
            continue
        a.langue = detecter_langue(a.titre, a.langue)
        a.url_traduite = lien_traduit(a.url, a.langue, a.payant)
        if a.langue != "fr":
            a.titre_origine = a.titre  # le titre français est rédigé à l'édition (V2)
        motif = filtre.motif_rejet(a, par_id[a.source_id])
        ids_du_passage.add(a.id)
        if motif:
            categorie = motif.split(":")[0].split(" ")[0]  # « sport », « guerre », « url »…
            rapport.rejetes[categorie] = rapport.rejetes.get(categorie, 0) + 1
            vus[a.id] = _jour(maintenant)  # déjà jugé : on ne le réexamine pas
            continue
        nouveaux.append(a)

    refs = [(t["id"], t["t"]) for t in titres]
    dedup.grouper(nouveaux, refs)

    # Premier passage d'une source : on mémorise tout (sans alerte) et on ne garde que le récent.
    a_ecrire, a_alerter = [], []
    for a in nouveaux:
        vus[a.id] = _jour(maintenant)
        if a.source_id in premieres:
            recent = (
                a.publie_le and maintenant - datetime.fromisoformat(a.publie_le) <= BASELINE_FENETRE
            )
            if recent:
                a_ecrire.append(a)
        else:
            a_ecrire.append(a)
            a_alerter.append(a)
    rapport.nouveaux = len(a_ecrire)
    for a in a_ecrire:  # nouveauté : date d'observation si la page ne donne pas de date
        a.publie_le = a.publie_le or maintenant.isoformat()
    for sid in premieres:
        if stats.get(sid, {}).get("dernier_ok") == maintenant.isoformat():
            stats[sid]["premier_passage"] = maintenant.isoformat()
    for a in a_ecrire:
        stats[a.source_id]["dernier_nouvel_article"] = maintenant.isoformat()

    candidates = alertes.eligibles(a_alerter, par_id, maintenant)
    silence = alertes.en_plage_silencieuse(maintenant)
    jour = _jour(maintenant)
    en_attente: list[dict] = []

    def ecrire_etat(tx) -> None:
        nonlocal en_attente
        fichier = f"articles/{jour}.jsonl"
        deja = {
            json.loads(ligne)["id"] for ligne in (tx.lire(fichier, "") or "").splitlines() if ligne
        }
        lignes = [
            json.dumps(a.vers_dict(), ensure_ascii=False) for a in a_ecrire if a.id not in deja
        ]
        if lignes:
            tx.ajouter(fichier, lignes)
        # fusion avec l'état frais (une autre tâche a pu écrire entre-temps)
        coupe_vus = _jour(maintenant - timedelta(days=VUS_JOURS))
        frais_vus = {**json.loads(tx.lire("state/vus.json", "{}") or "{}"), **vus}
        tx.ecrire("state/vus.json", _json({k: v for k, v in frais_vus.items() if v >= coupe_vus}))
        coupe_t = _jour(maintenant - timedelta(days=TITRES_JOURS))
        frais_t = {t["id"]: t for t in json.loads(tx.lire("state/titres.json", "[]") or "[]")}
        for a in nouveaux:
            frais_t[a.id] = {"id": a.id, "t": dedup.titre_normalise(a.titre), "d": jour}
        tx.ecrire("state/titres.json", _json([t for t in frais_t.values() if t["d"] >= coupe_t]))
        coupe_g = _jour(maintenant - timedelta(days=VUS_JOURS))
        frais_g = {**json.loads(tx.lire("state/gnews.json", "{}") or "{}"), **cache_gn}
        tx.ecrire("state/gnews.json", _json({k: v for k, v in frais_g.items() if v[1] >= coupe_g}))
        frais_s = {**json.loads(tx.lire("state/sources.json", "{}") or "{}"), **stats}
        tx.ecrire("state/sources.json", _json(frais_s))
        attente = {
            a["id"]: a for a in json.loads(tx.lire("state/alertes_en_attente.json", "[]") or "[]")
        }
        for a in candidates:
            attente.setdefault(a.id, {**a.vers_dict(), "differe": silence})
        en_attente = list(attente.values())
        tx.ecrire("state/alertes_en_attente.json", _json(en_attente))
        limite = _jour(maintenant - timedelta(days=PURGE_ARTICLES_JOURS))
        for chemin in tx.lister("articles"):
            if chemin.removeprefix("articles/").removesuffix(".jsonl") < limite:
                tx.supprimer(chemin)

    etat.transaction("data: collecte", ecrire_etat)
    rapport.alertes_en_attente = len(en_attente)

    if en_attente and not silence and token and chat_id:
        corps = alertes.construire_message(
            en_attente, differe=any(a["differe"] for a in en_attente)
        )
        try:
            envoyer("alerte", corps, token=token, chat_id=chat_id, client=client, journal=journal)
        except Exception as exc:  # noqa: BLE001 - l'alerte reste en attente, reprise au passage suivant
            journal.erreur("alerte_echec", journal.masquer(str(exc))[:200])
        else:
            rapport.alertes_envoyees = len(en_attente)
            envoyees = {a["id"] for a in en_attente}
            etat.transaction(
                "data: alertes envoyées",
                lambda tx: tx.ecrire(
                    "state/alertes_en_attente.json",
                    _json(
                        [
                            a
                            for a in json.loads(
                                tx.lire("state/alertes_en_attente.json", "[]") or "[]"
                            )
                            if a["id"] not in envoyees
                        ]
                    ),
                ),
            )
            rapport.alertes_en_attente = 0

    journal.info(
        "collecte_terminee",
        f"{rapport.nouveaux} nouveau(x), {rapport.alertes_envoyees} alerte(s)",
        sources_ok=rapport.sources_ok,
        sources_en_erreur=len(rapport.sources_en_erreur),
        lus=rapport.lus,
        rejetes=sum(rapport.rejetes.values()),
        resolutions=rapport.resolutions,
        resolutions_echec=rapport.resolutions_echec,
    )
    return rapport


def _json(valeur) -> str:
    return json.dumps(valeur, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
