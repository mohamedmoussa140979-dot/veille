"""Un passage de collecte de bout en bout, sans réseau, sur des pages réelles enregistrées."""

import json
from datetime import UTC, datetime
from pathlib import Path

from tests.conftest import FausseReponse
from veille.collecte.filtre import Filtre
from veille.collecte.orchestrateur import collecter
from veille.config import RACINE, charger_regles_filtre
from veille.etat import EtatLocal
from veille.http import ErreurReseau
from veille.journal import Journal

FIX = Path(__file__).parent / "fixtures"
BCT_URL = "https://www.bct.gov.tn/bct/siteprod/index.jsp"
INS_URL = "https://www.ins.tn/communique-de-presse"
FITCH_URL = "https://news.google.com/rss/search?q=Fitch"


def source(id_, type_, url, **kw):
    base = {
        "id": id_, "nom": id_.upper(), "url": url, "type": type_, "chapitre": "eco-tunisie",
        "langue": "fr", "alerte": False, "payant": False, "actif": True,
    }  # fmt: skip
    return {**base, **kw}


SRC_BCT = source("bct", "bct", BCT_URL, alerte=True, filtre=False)
SRC_INS = source("ins", "ins", INS_URL)


class ClientParUrl:
    """Réponses par URL (modifiables entre deux passages) ; compte les appels."""

    def __init__(self, pages):
        self.pages = dict(pages)
        self.appels = []

    def get(self, url, **kw):
        self.appels.append(("GET", url))
        p = self.pages[url.split("?")[0] if url not in self.pages else url]
        if isinstance(p, Exception):
            raise p
        return p

    def post(self, url, **kw):
        self.appels.append(("POST", url))
        return self.pages[url]


def ok(nom):
    return FausseReponse(200, contenu=(FIX / nom).read_bytes())


def nouvelle_bct():
    """La page BCT du fixture + une actualité du jour (id 1290)."""
    html = (FIX / "bct_index.html").read_text(encoding="utf-8")
    neuf = (
        '<div class="slider-content"><div class="date">14-11-2026</div>'
        '<div class="description">Taux directeur : décision du Conseil d\'administration</div>'
        '<a class="button" href="actualites.jsp?id=1290">Lire la suite</a></div>'
    )
    return FausseReponse(
        200, contenu=html.replace("<div class='slider'>", "<div class='slider'>" + neuf).encode()
    )


def lancer(client, etat, maintenant, sources=(SRC_BCT, SRC_INS), envoyes=None, echec_envoi=False):
    journal = Journal(sortie=lambda _: None)

    def faux_envoyer(type_, corps, **kw):
        if echec_envoi:
            raise RuntimeError("Telegram indisponible")
        envoyes.append((type_, corps))

    return collecter(
        sources=list(sources),
        client=client,
        journal=journal,
        etat=etat,
        filtre=Filtre(charger_regles_filtre(RACINE / "config" / "exclusions.yaml")),
        maintenant=maintenant,
        token="t",
        chat_id="c",
        envoyer=faux_envoyer,
    ), journal


def utc(jour, h, m=0):
    return datetime(2026, 11, jour, h, m, tzinfo=UTC)


FEV = datetime(
    2026, 2, 3, 12, 0, tzinfo=UTC
)  # les articles Google News de la fixture datent du 02/02


def lignes(etat, jour):
    brut = etat.lire(f"articles/{jour}.jsonl") or ""
    return [json.loads(x) for x in brut.splitlines()]


# --- premier passage --------------------------------------------------------------------


def test_premier_passage_memorise_tout_sans_alerter(tmp_path):
    etat, envoyes = EtatLocal(tmp_path), []
    client = ClientParUrl({BCT_URL: ok("bct_index.html"), INS_URL: ok("ins.html")})
    rapport, _ = lancer(client, etat, utc(12, 19), envoyes=envoyes)  # 20:00 à Tunis
    assert rapport.sources_ok == 2 and not rapport.sources_en_erreur
    assert envoyes == []  # aucune alerte pour des articles déjà publiés
    # 3 BCT + 2 INS de moins de 14 jours sont mémorisés ; les 5 plus anciens sont écartés
    assert len(etat.lire_json("state/vus.json")) == 5
    stats = etat.lire_json("state/sources.json")
    assert "premier_passage" in stats["bct"] and stats["ins"]["n_dernier"] == 5
    # seuls les articles de moins de 24 h sont conservés pour l'édition : INS du 12/11 (00:00)
    assert [a["source_id"] for a in lignes(etat, "2026-11-12")] == ["ins"]


def test_deuxieme_passage_sans_nouveaute_ne_fait_rien(tmp_path):
    etat, envoyes = EtatLocal(tmp_path), []
    client = ClientParUrl({BCT_URL: ok("bct_index.html"), INS_URL: ok("ins.html")})
    lancer(client, etat, utc(12, 19), envoyes=envoyes)
    rapport, _ = lancer(client, etat, utc(13, 8), envoyes=envoyes)
    assert rapport.nouveaux == 0 and envoyes == []


# --- nouveauté et alertes ---------------------------------------------------------------


def test_nouvelle_publication_bct_declenche_une_alerte(tmp_path):
    etat, envoyes = EtatLocal(tmp_path), []
    client = ClientParUrl({BCT_URL: ok("bct_index.html"), INS_URL: ok("ins.html")})
    lancer(client, etat, utc(12, 19), envoyes=envoyes)
    client.pages[BCT_URL] = nouvelle_bct()
    rapport, _ = lancer(client, etat, utc(14, 9), envoyes=envoyes)  # 10:00 à Tunis
    assert rapport.nouveaux == 1 and rapport.alertes_envoyees == 1
    assert len(envoyes) == 1 and envoyes[0][0] == "alerte"
    assert "Taux directeur" in envoyes[0][1] and "actualites.jsp?id=1290" in envoyes[0][1]
    assert etat.lire_json("state/alertes_en_attente.json") == []
    assert [a["titre"][:12] for a in lignes(etat, "2026-11-14")] == ["Taux directe"]


def test_a3_alerte_de_nuit_differee_a_sept_heures(tmp_path):
    etat, envoyes = EtatLocal(tmp_path), []
    client = ClientParUrl({BCT_URL: ok("bct_index.html"), INS_URL: ok("ins.html")})
    lancer(client, etat, utc(12, 19), envoyes=envoyes)
    client.pages[BCT_URL] = nouvelle_bct()
    # 23:15 à Tunis : plage silencieuse -> rien n'est envoyé, l'alerte attend
    rapport, _ = lancer(client, etat, utc(14, 22, 15), envoyes=envoyes)
    assert envoyes == [] and rapport.alertes_en_attente == 1
    assert etat.lire_json("state/alertes_en_attente.json")[0]["differe"] is True
    # 05:15 à Tunis : toujours silencieux
    lancer(client, etat, utc(15, 4, 15), envoyes=envoyes)
    assert envoyes == []
    # 07:15 à Tunis : un message groupé part, la file se vide
    rapport, _ = lancer(client, etat, utc(15, 6, 15), envoyes=envoyes)
    assert len(envoyes) == 1 and envoyes[0][1].startswith("Détectées pendant la plage silencieuse")
    assert rapport.alertes_en_attente == 0


def test_alerte_conservee_si_telegram_est_en_panne(tmp_path):
    etat, envoyes = EtatLocal(tmp_path), []
    client = ClientParUrl({BCT_URL: ok("bct_index.html"), INS_URL: ok("ins.html")})
    lancer(client, etat, utc(12, 19), envoyes=envoyes)
    client.pages[BCT_URL] = nouvelle_bct()
    rapport, journal = lancer(client, etat, utc(14, 9), envoyes=envoyes, echec_envoi=True)
    assert (
        rapport.alertes_envoyees == 0 and len(etat.lire_json("state/alertes_en_attente.json")) == 1
    )
    assert journal.avec_niveau("erreur")[0]["code"] == "alerte_echec"
    rapport, _ = lancer(client, etat, utc(14, 11), envoyes=envoyes)  # Telegram revenu
    assert rapport.alertes_envoyees == 1 and len(envoyes) == 1


def test_une_source_sans_alerte_n_alerte_jamais(tmp_path):
    etat, envoyes = EtatLocal(tmp_path), []
    client = ClientParUrl({BCT_URL: ok("bct_index.html"), INS_URL: ok("ins.html")})
    lancer(client, etat, utc(12, 19), sources=(SRC_BCT,), envoyes=envoyes)
    lancer(
        client, etat, utc(13, 9), sources=(SRC_BCT, SRC_INS), envoyes=envoyes
    )  # INS : 1er passage
    assert envoyes == []


# --- pannes -----------------------------------------------------------------------------


def test_une_source_en_panne_n_arrete_pas_les_autres(tmp_path):
    etat, envoyes = EtatLocal(tmp_path), []
    client = ClientParUrl({BCT_URL: ErreurReseau("connexion fermée"), INS_URL: ok("ins.html")})
    rapport, journal = lancer(client, etat, utc(12, 19), envoyes=envoyes)
    assert rapport.sources_ok == 1 and "bct" in rapport.sources_en_erreur
    stats = etat.lire_json("state/sources.json")
    assert stats["bct"]["erreurs_consecutives"] == 1 and "premier_passage" not in stats["bct"]
    assert journal.avec_niveau("avertissement")[0]["code"] == "source_en_erreur"


def test_source_en_panne_au_premier_passage_reste_en_baseline(tmp_path):
    """Pas de rafale d'alertes quand la source revient après une panne initiale."""
    etat, envoyes = EtatLocal(tmp_path), []
    client = ClientParUrl({BCT_URL: FausseReponse(503), INS_URL: ok("ins.html")})
    lancer(client, etat, utc(12, 19), envoyes=envoyes)
    client.pages[BCT_URL] = ok("bct_index.html")
    lancer(client, etat, utc(13, 9), envoyes=envoyes)
    assert envoyes == []


def test_page_changee_est_une_erreur_et_non_un_zero_nouveaute(tmp_path):
    etat = EtatLocal(tmp_path)
    client = ClientParUrl(
        {
            BCT_URL: FausseReponse(200, contenu=b"<html><body>Maintenance</body></html>"),
            INS_URL: ok("ins.html"),
        }
    )
    rapport, _ = lancer(client, etat, utc(12, 19), envoyes=[])
    assert "bct" in rapport.sources_en_erreur


# --- filtre, doublons, âge --------------------------------------------------------------


def test_filtre_editorial_rejette_et_memorise(tmp_path):
    etat = EtatLocal(tmp_path)
    page = FausseReponse(
        200,
        contenu=(FIX / "html_generique.html")
        .read_bytes()
        .replace("Tunisie Numérique</title>".encode(), "Tunisie Numérique</title>".encode()),
    )
    html = page.content.decode().replace(
        "<nav>",
        '<h3><a href="https://www.tunisienumerique.com/football-le-derby-de-tunis-oppose-deux-clubs">'
        "Football : le derby de Tunis oppose les deux clubs ce soir</a></h3><nav>",
    )
    src = source("tn", "html-generique", "https://www.tunisienumerique.com/")
    client = ClientParUrl({src["url"]: FausseReponse(200, contenu=html.encode())})
    rapport, _ = lancer(client, etat, utc(12, 19), sources=(src,), envoyes=[])
    assert rapport.rejetes.get("url", 0) >= 1  # l'article de football est rejeté (rubrique)
    assert not any("derby" in a["titre"] for a in lignes(etat, "2026-11-12"))


def test_meme_fait_deux_sources_un_seul_groupe_une_seule_alerte(tmp_path):
    etat, envoyes = EtatLocal(tmp_path), []
    bct2 = source(
        "bct2", "bct", "https://www.bct.gov.tn/bct/siteprod/index2.jsp", alerte=True, filtre=False
    )
    client = ClientParUrl({BCT_URL: ok("bct_index.html"), bct2["url"]: ok("bct_index.html")})
    lancer(client, etat, utc(12, 19), sources=(SRC_BCT, bct2), envoyes=envoyes)
    client.pages[BCT_URL] = nouvelle_bct()
    client.pages[bct2["url"]] = nouvelle_bct()  # même titre, URL propre à chaque source
    html = client.pages[bct2["url"]].content.decode().replace("id=1290", "id=2290")
    client.pages[bct2["url"]] = FausseReponse(200, contenu=html.encode())
    rapport, _ = lancer(client, etat, utc(14, 9), sources=(SRC_BCT, bct2), envoyes=envoyes)
    articles = lignes(etat, "2026-11-14")
    assert len(articles) == 2 and articles[1]["groupe"] == articles[0]["id"]
    assert envoyes[0][1].count("<b>") == 1  # une seule alerte pour le fait


def test_articles_de_plus_de_14_jours_ecartes(tmp_path):
    etat = EtatLocal(tmp_path)
    client = ClientParUrl({BCT_URL: ok("bct_index.html")})
    rapport, _ = lancer(
        client, etat, utc(15, 9).replace(month=12, day=20), sources=(SRC_BCT,), envoyes=[]
    )
    assert rapport.nouveaux == 0 and etat.lire_json("state/vus.json") == {}


# --- Google News ------------------------------------------------------------------------

PAGE_ARTICLE = '<c-wiz><div data-n-a-sg="SIG" data-n-a-ts="1770000000"></div></c-wiz>'


def reponse_batch(url):
    corps = json.dumps([["wrb.fr", "Fbv4je", json.dumps(["garturlres", url, 1]), None]])
    return FausseReponse(200, texte=f")]}}'\n\n{corps}\n")


def test_liens_google_news_resolus_une_seule_fois_et_traduits(tmp_path):
    etat = EtatLocal(tmp_path)
    src = source("fitch", "google-news", FITCH_URL, langue="en", filtre=False)
    flux = (FIX / "gnews_fitch.xml").read_text(encoding="utf-8")
    import re

    liens = re.findall(r"<link>(https://news\.google\.com/rss/articles/[^<]+)</link>", flux)
    pages = {FITCH_URL: FausseReponse(200, contenu=flux.encode())}
    for lien in liens:
        ident = re.search(r"/articles/([^?/]+)", lien).group(1)
        pages[f"https://news.google.com/rss/articles/{ident}"] = FausseReponse(
            200, texte=PAGE_ARTICLE
        )
    n = {"i": 0}

    class Client(ClientParUrl):
        def post(self, url, **kw):
            self.appels.append(("POST", url))
            n["i"] += 1
            return reponse_batch(
                f"https://media{n['i']}.example.org/article-{n['i']}?utm_source=gn"
            )

    client = Client(pages)
    rapport, _ = lancer(client, etat, FEV, sources=(src,), envoyes=[])
    posts = [a for a in client.appels if a[0] == "POST"]
    assert rapport.resolutions == len(posts) > 0 and rapport.resolutions_echec == 0
    # les articles trop anciens (> 14 jours) ne sont même pas résolus
    assert len(posts) < len(liens)
    articles = lignes(etat, "2026-02-03")
    # au premier passage : articles de moins de 24 h conservés, les autres seulement mémorisés
    assert articles and rapport.nouveaux == len(articles) <= len(posts)
    for a in articles:
        assert "news.google.com" not in a["url"] and "utm_" not in a["url"]  # A4
        assert a["langue"] == "en" and a["url_traduite"].startswith("https://media")
        assert ".translate.goog/" in a["url_traduite"] and "_x_tr_tl=fr" in a["url_traduite"]  # A12
        assert a["titre_origine"] == a["titre"]
    # articles plus vieux que la fenêtre de démarrage : non résolus, mémorisés (URL vide)
    cache = etat.lire_json("state/gnews.json")
    assert any(v[0] == "" for v in cache.values()) and any(v[0] for v in cache.values())
    # second passage : tout est en cache, aucune nouvelle résolution, aucune nouveauté
    client.appels.clear()
    rapport, _ = lancer(client, etat, FEV.replace(hour=20), sources=(src,), envoyes=[])
    assert [a for a in client.appels if a[0] == "POST"] == [] and rapport.nouveaux == 0


def test_lien_google_news_non_resolu_ecarte_l_article(tmp_path):
    etat = EtatLocal(tmp_path)
    src = source("fitch", "google-news", FITCH_URL, langue="en", filtre=False)
    flux = (FIX / "gnews_fitch.xml").read_text(encoding="utf-8")
    import re

    pages = {FITCH_URL: FausseReponse(200, contenu=flux.encode())}
    for lien in re.findall(r"<link>(https://news\.google\.com/rss/articles/[^<]+)</link>", flux):
        ident = re.search(r"/articles/([^?/]+)", lien).group(1)
        pages[f"https://news.google.com/rss/articles/{ident}"] = FausseReponse(
            200, texte="<html>refus</html>"
        )
    rapport, _ = lancer(ClientParUrl(pages), etat, FEV, sources=(src,), envoyes=[])
    assert rapport.nouveaux == 0 and rapport.resolutions_echec > 0
    assert etat.lire_json("state/vus.json") == {}  # non résolu : on réessaiera au passage suivant


# --- purge ------------------------------------------------------------------------------


def test_purge_des_articles_de_plus_de_90_jours_et_des_vus_de_plus_de_60_jours(tmp_path):
    etat = EtatLocal(tmp_path)
    etat.ajouter_lignes("articles/2026-06-01.jsonl", ['{"id": "x"}'])
    etat.ajouter_lignes("articles/2026-11-01.jsonl", ['{"id": "y"}'])
    etat.modifier_json(
        "state/vus.json", lambda d: {"vieux": "2026-08-01", "recent": "2026-11-10"}, defaut={}
    )
    client = ClientParUrl({INS_URL: ok("ins.html")})
    lancer(client, etat, utc(14, 9), sources=(SRC_INS,), envoyes=[])
    assert etat.lire("articles/2026-06-01.jsonl") is None
    assert etat.lire("articles/2026-11-01.jsonl") is not None
    vus = etat.lire_json("state/vus.json")
    assert "vieux" not in vus and "recent" in vus
