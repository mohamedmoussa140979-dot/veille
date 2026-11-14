"""V4 : veille AWB (collecte, score, regroupement, traduction, message) — sans réseau."""

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests.conftest import FausseReponse, FauxClient
from tests.test_telegram import equilibre
from veille.awb import __main__ as cli
from veille.awb import collecte, config
from veille.awb.message import article, construire_message, niveau
from veille.awb.traduction import Traducteur
from veille.etat import EtatGit, EtatLocal
from veille.http import ErreurReseau
from veille.journal import Journal

FIX = Path(__file__).parent / "fixtures"
MAINT = datetime(2026, 2, 3, 12, 0, tzinfo=UTC)  # lendemain des articles Fitch de la fixture


def cfg():
    return config.charger()


def sujet(**kw):
    base = {
        "tag": "🟩 SOUV", "locales": [("en", "US", "US:en")], "seuil": 8, "fenetre_h": 48,
        "motif": re.compile(r"tunisi|fitch", re.I), "motif_et": None, "requetes": {"x": 9},
    }  # fmt: skip
    return {**base, **kw}


def flux(nom="gnews_fitch.xml"):
    return (FIX / nom).read_bytes()


def lire(c, s=None, **kw):
    s = s or sujet()
    return collecte.lire_flux(
        flux(), c, s, 9, "GNews US", MAINT - timedelta(hours=s["fenetre_h"]), "en", MAINT, **kw
    )


# --- configuration ----------------------------------------------------------------------


def test_configuration_reprise_de_l_ancien_script():
    c = cfg()
    assert [s["tag"] for s in c["sujets"]] == ["🟦 AWB", "🟨 TN", "🟩 SOUV", "🟩 SOUV", "🟪 TECH"]
    assert sum(len(s["requetes"]) for s in c["sujets"]) == 48
    assert len(c["signaux"]) == 21 and c["max_envois"] == 30
    tech = c["sujets"][4]
    assert tech["locales"] == [] and tech["seuil"] == 18 and len(tech["gdelt"]) == 8
    assert tech["flux"][0]["nom"] == "Finextra"
    assert c["sujets"][2]["motif_et"] is not None  # les sujets souverains exigent un signal macro


def test_urls_de_requete():
    u = collecte.gnews_url('"Attijariwafa bank"', "fr", "MA", "MA:fr")
    assert u.startswith("https://news.google.com/rss/search?q=%22Attijariwafa+bank%22+when:2d")
    assert "hl=fr&gl=MA&ceid=MA:fr" in u
    g = collecte.gdelt_url("stablecoin AND bank", 24)
    assert "sourcelang%3Aenglish" in g and "timespan=24h" in g and "format=rss" in g


# --- lecture et filtres -----------------------------------------------------------------


def test_lecture_titre_media_date_score_et_evenement():
    items = lire(cfg())
    assert items and all(
        i["tag"] == "🟩 SOUV" and i["date"] >= MAINT - timedelta(hours=48) for i in items
    )
    a = next(i for i in items if "Fitch watch list" in i["titre"])
    assert a["source"] == "APAnews - Agence de Presse Africaine"
    assert a["score"] >= 9 + 6  # poids de la requête + signal « Fitch »
    assert a["evenement"] == "ev:fitch:tn"


def test_filtres_bruit_publicite_source_exclue_motif_et_fenetre():
    c = cfg()
    assert lire(c, sujet(motif=re.compile("zzzjamais"))) == []
    assert lire(c, sujet(motif_et=re.compile("zzzjamais")), strict=True) == []  # exigence absente
    assert lire(c, sujet(motif_et=re.compile("zzzjamais")), strict=False)  # flux « curés »
    vieux = collecte.lire_flux(flux(), c, sujet(), 9, "x", MAINT, "en", MAINT)  # fenêtre vide
    assert vieux == []
    c2 = {**c, "sources_exclues": re.compile("apanews", re.I)}
    assert all("APAnews" not in i["source"] for i in lire(c2))
    c3 = {**c, "bruit": re.compile("fitch", re.I)}
    assert lire(c3) == []
    c4 = {**c, "publicite": re.compile("fitch", re.I)}
    assert lire(c4) == []


def test_bonus_pour_les_sources_de_qualite():
    c = cfg()
    sans = lire({**c, "sources_qualite": re.compile("zzz")})
    avec = lire({**c, "sources_qualite": re.compile("apanews", re.I)})
    s0 = next(i for i in sans if i["source"].startswith("APAnews"))
    s1 = next(i for i in avec if i["source"].startswith("APAnews"))
    assert s1["score"] == s0["score"] + 4


def test_resume_utile_et_titre_propre():
    assert collecte.resume_utile("Titre", "x" * 80)
    assert not collecte.resume_utile("Titre", "court")
    assert not collecte.resume_utile(
        "La BCT relève son taux", "La BCT relève son taux directeur " + "x" * 40
    )
    assert (
        collecte.titre_propre("La BCT relève son taux - Business News", "Business News")
        == "La BCT relève son taux"
    )
    assert collecte.cle_titre("La BCT relève - Reuters") == collecte.cle_titre(
        "La BCT relève - Bloomberg"
    )


def test_evenement_acteur_x_pays():
    c = cfg()
    assert collecte.cle_evenement(c, "Moody's relève la note de la Tunisie") == "ev:moody:tn"
    assert collecte.cle_evenement(c, "Fitch confirme la note du Maroc") == "ev:fitch:ma"
    assert collecte.cle_evenement(c, "Une banque lance une application") is None


# --- sélection : doublons, événements, seuil --------------------------------------------


def item(titre, score=20, ev=None, tag="🟩 SOUV", seuil=13, minutes=0):
    return {"cle": collecte.cle_titre(titre), "titre": titre, "lien": "https://e.test/" + titre[:5], "resume": "",
            "tag": tag, "source": "Src", "date": MAINT - timedelta(minutes=minutes), "score": score,
            "seuil": seuil, "langue": "en", "evenement": ev}  # fmt: skip


def test_selection_un_article_par_titre_et_au_dessus_du_seuil():
    a, b, bas = item("Titre A", 20), item("Titre A", 25), item("Titre bas", 5)
    retenus, uniques = collecte.selectionner(cfg(), [a, b, bas], {}, int(MAINT.timestamp()))
    assert [r["score"] for r in retenus] == [25]  # le meilleur des doublons, le bas score écarté
    assert len(uniques) == 2  # « bas » est mémorisé comme vu même s'il n'est pas envoyé


def test_selection_un_seul_message_par_evenement_et_fenetre_de_72_heures():
    ts = int(MAINT.timestamp())
    a, b = (
        item("Moody's et la Tunisie 1", 20, "ev:moody:tn"),
        item("Moody's et la Tunisie 2", 24, "ev:moody:tn"),
    )
    retenus, _ = collecte.selectionner(cfg(), [a, b], {}, ts)
    assert [r["titre"] for r in retenus] == ["Moody's et la Tunisie 2"]
    recent = {"ev:moody:tn": ts - 3600}
    assert collecte.selectionner(cfg(), [a], recent, ts)[0] == []  # déjà traité il y a 1 h
    ancien = {"ev:moody:tn": ts - 73 * 3600}
    assert len(collecte.selectionner(cfg(), [a], ancien, ts)[0]) == 1  # au-delà de 72 h
    assert collecte.selectionner(cfg(), [a], {a["cle"]: ts - 10}, ts)[0] == []  # déjà envoyé


def test_selection_trie_par_sujet_puis_score():
    items = [
        item("B1", 15, tag="🟨 TN"),
        item("A1", 15, tag="🟦 AWB"),
        item("A2", 30, tag="🟦 AWB"),
    ]
    retenus, _ = collecte.selectionner(cfg(), items, {}, int(MAINT.timestamp()))
    assert [r["titre"] for r in retenus] == ["A2", "A1", "B1"]


# --- traduction -------------------------------------------------------------------------


def gtx(texte):
    return FausseReponse(200, json_=[[[texte, "src", None, None, 1]], None, "en"])


def test_traduction_gtx_nominale_cache_et_francais_inchange():
    c = FauxClient([gtx("La banque centrale lance un système")])
    t = Traducteur(c, Journal(sortie=lambda _: None))
    assert (
        t.traduire("The central bank rolled out a system", "en")
        == "La banque centrale lance un système"
    )
    assert (
        t.traduire("The central bank rolled out a system", "en")
        == "La banque centrale lance un système"
    )
    assert len(c.appels) == 1 and (t.demandees, t.reussies) == (1, 1)  # cache
    assert t.traduire("Déjà français", "fr") == "Déjà français" and len(c.appels) == 1


def test_traduction_repli_gtx_clients5_mymemory_puis_texte_d_origine():
    j = Journal(sortie=lambda _: None)
    c = FauxClient(
        [FausseReponse(429), FausseReponse(200, json_=[["Bonjour"]])]
    )  # gtx KO, clients5 OK
    assert Traducteur(c, j).traduire("Hello", "en") == "Bonjour"
    c = FauxClient([FausseReponse(429), FausseReponse(500),
                    FausseReponse(200, json_={"responseData": {"translatedText": "Salut"}})])  # fmt: skip
    assert Traducteur(c, j).traduire("Hi", "en") == "Salut"
    c = FauxClient(
        [FausseReponse(429), ErreurReseau("x"), FausseReponse(200, json_={"responseData": {}})]
    )
    t = Traducteur(c, j)
    assert t.traduire("Untranslatable", "en") == "Untranslatable"  # tout a échoué : original
    assert (t.demandees, t.reussies) == (
        1,
        0,
    )  # base du contrôle de santé « traduction sans donnée »


def test_gtx_abandonne_apres_trois_echecs():
    c = FauxClient([FausseReponse(429), FausseReponse(200, json_=[["a"]])] * 3
                   + [FausseReponse(200, json_=[["d"]])])  # fmt: skip
    t = Traducteur(c, Journal(sortie=lambda _: None))
    for mot in ("un", "deux", "trois"):
        t.traduire(mot, "en")
    t.traduire("quatre", "en")
    assert "translate.googleapis.com" not in c.appels[-1]["url"]  # 4e texte : clients5 directement


def test_le_texte_est_plafonne_a_450_caracteres():
    c = FauxClient([gtx("ok")])
    Traducteur(c, Journal(sortie=lambda _: None)).traduire("x" * 1000, "en")
    assert "x" * 450 in c.appels[0]["url"] and "x" * 451 not in c.appels[0]["url"]


# --- message ----------------------------------------------------------------------------


class TraducteurFixe:
    demandees = reussies = 0

    def traduire(self, texte, source="auto"):
        return f"FR:{texte}" if source != "fr" else texte


def vrai_item(**kw):
    base = item("Fitch affirms Tunisia at CCC+ - Reuters", 26, "ev:fitch:tn") | {
        "source": "Reuters", "lien": "https://www.techcabal.com/a?id=1", "langue": "en",
        "resume": "Fitch Ratings affirmed the sovereign rating of Tunisia and revised the outlook to stable " + "x" * 30,
    }  # fmt: skip
    if "titre" in kw:
        base["cle"] = collecte.cle_titre(kw["titre"])
    return {**base, **kw}


def test_article_titre_francais_titre_d_origine_resume_et_liens():
    bloc = article(vrai_item(), TraducteurFixe())
    assert bloc.startswith("🔴 <b>FR:Fitch affirms Tunisia at CCC+</b>")
    assert "<i>Fitch affirms Tunisia at CCC+</i>" in bloc  # titre d'origine conservé
    assert "FR:Fitch Ratings affirmed" in bloc  # résumé traduit
    assert "Reuters · 03/02 11:00 · score 26" in bloc or "Reuters · 03/02 13:00 · score 26" in bloc
    assert "🇫🇷 Lire en français" in bloc and "translate.goog" in bloc and "🔗 Source" in bloc
    assert equilibre(bloc)


def test_article_francais_sans_lien_traduit_et_niveaux():
    bloc = article(
        vrai_item(langue="fr", resume="", titre="Attijariwafa bank publie ses résultats"),
        TraducteurFixe(),
    )
    assert "🇫🇷" not in bloc and "FR:" not in bloc
    assert (niveau(30), niveau(20), niveau(10)) == ("🔴", "🟠", "⚪️")


def test_message_groupe_par_sujet_une_seule_fois_chaque_titre_de_section():
    items = [
        vrai_item(tag="🟦 AWB"),
        vrai_item(tag="🟦 AWB", titre="Autre"),
        vrai_item(tag="🟩 SOUV"),
    ]
    m = construire_message(items, TraducteurFixe())
    assert m.count("<b>🟦 AWB</b>") == 1 and m.count("<b>🟩 SOUV</b>") == 1
    assert m.index("🟦 AWB") < m.index("🟩 SOUV") and equilibre(m)


def test_titre_hostile_echappe():
    m = construire_message([vrai_item(titre="<script>x</script> & Co")], TraducteurFixe())
    assert "<script>" not in m and "&lt;script&gt;" in m


# --- passage complet --------------------------------------------------------------------


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    etat = EtatLocal(tmp_path / "etat")
    monkeypatch.setattr(EtatGit, "depuis_environnement", classmethod(lambda cls, *a, **k: etat))
    envoyes = []
    monkeypatch.setattr(cli, "envoyer", lambda type_, corps, **kw: envoyes.append((type_, corps)))
    monkeypatch.setattr("veille.temps.maintenant", lambda: MAINT)
    monkeypatch.setenv("TG_TOKEN_VEILLE", "jeton-de-test")
    monkeypatch.setenv("TG_CHAT_ID", "42")

    def avec_items(items, erreurs=None):
        monkeypatch.setattr(
            cli,
            "collecter",
            lambda *a, **k: (items, erreurs or {"gnews": 0, "gdelt": 0, "flux": 0}),
        )

    class FauxTraducteur(TraducteurFixe):
        def __init__(self, *a, **k):
            pass

    monkeypatch.setattr(cli, "Traducteur", FauxTraducteur)
    return etat, envoyes, avec_items, monkeypatch


def test_passage_envoie_un_message_marque_les_articles_et_ne_renvoie_pas(env):
    etat, envoyes, avec_items, _ = env
    avec_items([vrai_item(), vrai_item(titre="Autre titre sans rapport", evenement=None, score=30)])
    assert cli.main([]) == 0
    assert len(envoyes) == 1 and envoyes[0][0] == "awb"
    vus = etat.lire_json("state/awb_vus.json")
    assert len(vus) >= 3 and "ev:fitch:tn" in vus  # titres + événement mémorisés
    assert etat.lire_json("state/awb.json")["envoyes"] == 2
    assert cli.main([]) == 0 and len(envoyes) == 1  # même articles : rien de nouveau


def test_telegram_en_panne_les_articles_ne_sont_pas_marques_envoyes(env):
    etat, envoyes, avec_items, mp = env
    avec_items([vrai_item(score=14, tag="🟨 TN", seuil=8) | {"seuil": 8}])

    def panne(*a, **k):
        raise RuntimeError("indisponible")

    mp.setattr(cli, "envoyer", panne)
    assert cli.main([]) == 0
    vus = etat.lire_json("state/awb_vus.json")
    # l'article est « vu » (non renvoyé tel quel) mais pas son événement : un réessai reste possible
    assert "ev:fitch:tn" not in vus and etat.lire_json("state/awb.json")["envoyes"] == 0


def test_rien_a_envoyer_aucun_message(env):
    etat, envoyes, avec_items, _ = env
    avec_items([vrai_item(score=1)])
    assert cli.main([]) == 0 and envoyes == []


def test_liens_google_news_resolus_ou_article_ecarte(env):
    etat, envoyes, avec_items, mp = env
    gn = "https://news.google.com/rss/articles/CBMiXYZ?oc=5"
    avec_items(
        [
            vrai_item(lien=gn, titre="Premier sujet AWB"),
            vrai_item(lien=gn.replace("XYZ", "ABC"), titre="Second sujet"),
        ]
    )
    mp.setattr(
        cli,
        "resoudre_google_news",
        lambda client, url, journal=None: (
            "https://reel.example.org/a?utm_source=x" if "XYZ" in url else None
        ),
    )
    assert cli.main([]) == 0
    corps = envoyes[0][1]
    assert "news.google.com" not in corps and "utm_" not in corps and "reel.example.org/a" in corps
    assert "Second sujet" not in corps  # lien non résolu : écarté
    assert etat.lire_json("state/gnews.json")["CBMiXYZ"][0].startswith("https://reel.example.org")


def test_traduction_sans_donnee_alerte_sante(env):
    etat, envoyes, avec_items, mp = env

    class TraducteurMuet(TraducteurFixe):
        def __init__(self, *a, **k):
            self.demandees, self.reussies = 3, 0

    mp.setattr(cli, "Traducteur", TraducteurMuet)
    avec_items([vrai_item()])
    cli.main([])
    sante = etat.lire("sante/2026-02.jsonl") or ""
    assert "awb_traduction_sans_donnee" in sante


def test_flux_en_erreur_resume_dans_le_journal_de_sante(env):
    etat, envoyes, avec_items, _ = env
    avec_items([], {"gnews": 2, "gdelt": 8, "flux": 1})
    cli.main([])
    sante = etat.lire("sante/2026-02.jsonl") or ""
    assert "awb_flux_en_erreur_resume" in sante and '"gdelt": 8' in sante.replace("\\", "")


@pytest.mark.parametrize(
    "donnees, attendu",
    [
        (["Bonjour"], "Bonjour"),
        ([["Bonjour", "en"]], "Bonjour"),
        ([["Bonjour", "en"], ["le monde", "en"]], "Bonjourle monde"),
        ([[["Bonjour", "Hello"], ["le monde", "world"]]], "Bonjourle monde"),
        ([], ""),
        ({"x": 1}, ""),
    ],
)
def test_extraction_clients5_formes_observees(donnees, attendu):
    from veille.awb.traduction import extraire_clients5

    assert extraire_clients5(donnees) == attendu
