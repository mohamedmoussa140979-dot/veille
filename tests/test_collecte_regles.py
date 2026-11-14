"""Liens, filtre éditorial, déduplication, alertes : tests sans réseau."""

from datetime import UTC, datetime

from tests.conftest import FausseReponse, FauxClient
from veille.collecte import alertes, dedup
from veille.collecte.article import Article, cle_url, id_article, nettoyer_url
from veille.collecte.filtre import Filtre
from veille.collecte.liens import (
    detecter_langue,
    est_google_news,
    lien_traduit,
    lien_traduit_repli,
    resoudre_google_news,
)
from veille.config import RACINE, charger_regles_filtre
from veille.http import ErreurReseau
from veille.journal import Journal


def art(titre, url="https://exemple.tn/a", source_id="s", **kw):
    return Article(source_id=source_id, source="Source", titre=titre, url=url, **kw)


# --- URL --------------------------------------------------------------------------------


def test_parametres_de_suivi_retires():
    sale = "https://exemple.tn/a?id=7&utm_source=x&fbclid=abc&gclid=1&utm_medium=y#haut"
    assert nettoyer_url(sale) == "https://exemple.tn/a?id=7"
    assert "utm_" not in nettoyer_url("https://x.tn/?utm_campaign=z")


def test_meme_article_meme_cle_malgre_www_slash_et_suivi():
    a = "https://www.exemple.tn/actu/1/?utm_source=tg"
    b = "https://exemple.tn/actu/1"
    assert cle_url(a) == cle_url(b) and id_article(a) == id_article(b)
    assert id_article("https://exemple.tn/actu/2") != id_article(b)


# --- lien traduit (V41) -----------------------------------------------------------------


def test_lien_traduit_forme_translate_goog():
    u = lien_traduit("https://www.reuters.com/markets/tunisia-2026", "en", False)
    assert u == (
        "https://www-reuters-com.translate.goog/markets/tunisia-2026"
        "?_x_tr_sl=en&_x_tr_tl=fr&_x_tr_hl=fr"
    )


def test_lien_traduit_tirets_doubles_et_requete_conservee():
    u = lien_traduit("https://my-site.tn/page.php?id=5", "ar", False)
    assert u == (
        "https://my--site-tn.translate.goog/page.php?id=5&_x_tr_sl=ar&_x_tr_tl=fr&_x_tr_hl=fr"
    )


def test_pas_de_lien_traduit_pour_francais_payant_google_news_et_domaines_bloques():
    assert lien_traduit("https://exemple.tn/a", "fr", False) is None
    assert lien_traduit("https://exemple.com/a", "en", True) is None  # source payante
    assert lien_traduit("https://news.google.com/rss/articles/xyz", "en", False) is None
    assert lien_traduit("https://www.ft.com/content/1", "en", False) is None
    assert lien_traduit("https://www.finextra.com/news/1", "en", False) is None


def test_lien_de_repli():
    assert lien_traduit_repli("https://a.com/x?y=1", "en") == (
        "https://translate.google.com/translate?sl=en&tl=fr&u=https%3A%2F%2Fa.com%2Fx%3Fy%3D1"
    )


def test_detection_de_la_langue_arabe():
    assert detecter_langue("هيئة السوق المالية تنشر تقريرها", "fr") == "ar"
    assert detecter_langue("Le CMF publie son rapport", "fr") == "fr"
    assert detecter_langue("BCT : taux directeur 7 %", "fr") == "fr"


# --- résolution Google News -------------------------------------------------------------

PAGE_ARTICLE = '<c-wiz><div data-n-a-sg="SIGNATURE" data-n-a-ts="1770000000"></div></c-wiz>'
LIEN_GN = "https://news.google.com/rss/articles/CBMiABC123?oc=5"


def reponse_batch(url):
    import json

    corps = json.dumps([["wrb.fr", "Fbv4je", json.dumps(["garturlres", url, 1]), None]])
    return FausseReponse(200, texte=f")]}}'\n\n{corps}\n")


def test_resolution_google_news_nominale():
    client = FauxClient(
        [FausseReponse(200, texte=PAGE_ARTICLE), reponse_batch("https://apanews.net/x")]
    )
    assert resoudre_google_news(client, LIEN_GN) == "https://apanews.net/x"
    assert client.appels[0]["url"] == "https://news.google.com/rss/articles/CBMiABC123"
    corps = client.appels[1]["data"]
    assert (
        corps.startswith("f.req=")
        and "SIGNATURE" in corps.replace("%22", '"')
        and "1770000000" in corps
    )


def test_resolution_echec_page_sans_signature_renvoie_none():
    j = Journal(sortie=lambda _: None)
    client = FauxClient([FausseReponse(200, texte="<html>consentement</html>")])
    assert resoudre_google_news(client, LIEN_GN, j) is None
    assert j.avec_niveau("avertissement")[0]["code"] == "gnews_resolution_echec"


def test_resolution_reseau_en_panne_et_reponse_incomprise():
    assert resoudre_google_news(FauxClient([ErreurReseau("boum")]), LIEN_GN) is None
    c = FauxClient(
        [FausseReponse(200, texte=PAGE_ARTICLE), FausseReponse(200, texte="n'importe quoi")]
    )
    assert resoudre_google_news(c, LIEN_GN) is None


def test_resolution_refuse_un_lien_qui_reste_google_news():
    c = FauxClient(
        [FausseReponse(200, texte=PAGE_ARTICLE), reponse_batch("https://news.google.com/x")]
    )
    assert resoudre_google_news(c, LIEN_GN) is None
    assert est_google_news("https://news.google.com/rss/articles/x")
    assert not est_google_news("https://apanews.net/")


# --- filtre éditorial -------------------------------------------------------------------


def filtre():
    return Filtre(charger_regles_filtre(RACINE / "config" / "exclusions.yaml"))


SRC = {"id": "s", "filtre": True}


def test_rejets_par_categorie_titre_et_resume():
    f = filtre()
    assert f.motif_rejet(art("L'Espérance remporte le derby de Tunis"), SRC) == "sport: derby"
    assert f.motif_rejet(art("Frappes aériennes sur la ville"), SRC).startswith("guerre")
    assert f.motif_rejet(art("Le festival de Carthage s'ouvre"), SRC).startswith("arts")
    assert f.motif_rejet(art("Titre neutre", resume="Un match très attendu"), SRC) == "sport: match"
    assert f.motif_rejet(art("Un séisme frappe la côte"), SRC).startswith("catastrophes")
    assert f.motif_rejet(art("Meurtre à Sfax : une enquête ouverte"), SRC).startswith(
        "faits_divers"
    )


def test_expressions_economiques_conservees():
    f = filtre()
    assert f.motif_rejet(art("Guerre commerciale : de nouveaux droits de douane"), SRC) is None
    assert f.motif_rejet(art("Le Club de Paris restructure la dette"), SRC) is None


def test_mots_entiers_seulement():
    f = filtre()
    assert (
        f.motif_rejet(art("Les footings du matin"), SRC) is None
    )  # « foot » n'est pas « footings »
    assert f.motif_rejet(art("Croissance : le PIB progresse de 1,2 %"), SRC) is None


def test_segments_d_url_exclus():
    f = filtre()
    a = art("Résultats de la journée", url="https://exemple.tn/sport/tunisie-1")
    assert f.motif_rejet(a, SRC) == "url /sport"


def test_source_exemptee_ne_filtre_pas():
    f = filtre()
    assert (
        f.motif_rejet(art("Guerre en Ukraine : la BCT et le FMI"), {"id": "bct", "filtre": False})
        is None
    )


def test_accents_et_casse_ignores():
    assert (
        filtre().motif_rejet(art("ÉQUIPE NATIONALE : liste des joueurs"), SRC).startswith("sport")
    )


# --- déduplication par titre proche -----------------------------------------------------


def test_meme_fait_plusieurs_sources_un_groupe():
    a = art("La BCT maintient son taux directeur à 7,5 %", url="https://a.tn/1")
    b = art("La BCT maintient son taux directeur à 7,5% - Business News", url="https://b.tn/2")
    c = art("Fitch confirme la note B de la Tunisie", url="https://c.tn/3")
    dedup.grouper([a, b, c])
    assert a.groupe == a.id and b.groupe == a.id
    assert c.groupe is None


def test_faits_differents_non_groupes():
    a = art("La BCT relève son taux directeur", url="https://a.tn/1")
    b = art("La BCT publie le rapport annuel sur la supervision bancaire", url="https://b.tn/2")
    dedup.grouper([a, b])
    assert a.groupe is None and b.groupe is None


def test_rapprochement_avec_les_jours_precedents():
    ancien = art("Fitch confirme la note B de la Tunisie", url="https://a.tn/1")
    nouveau = art("Fitch confirme la note B de la Tunisie", url="https://b.tn/2")
    dedup.grouper([nouveau], references=[(ancien.id, dedup.titre_normalise(ancien.titre))])
    assert nouveau.groupe == ancien.id


# --- alertes ----------------------------------------------------------------------------

SOURCES = {"bct": {"alerte": True}, "presse": {"alerte": False}}
MAINTENANT = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)


def test_plage_silencieuse_heure_de_tunis():
    def h(heure_utc, minute=0):
        return datetime(2026, 11, 14, heure_utc, minute, tzinfo=UTC)

    assert alertes.en_plage_silencieuse(h(21, 0))  # 22:00 à Tunis
    assert alertes.en_plage_silencieuse(h(3, 0))  # 04:00
    assert alertes.en_plage_silencieuse(h(5, 59))  # 06:59
    assert not alertes.en_plage_silencieuse(h(6, 0))  # 07:00
    assert not alertes.en_plage_silencieuse(h(20, 59))  # 21:59


def test_eligibilite_source_alerte_recente_un_seul_par_fait():
    a1 = art("Circulaire BCT n°1", source_id="bct", publie_le="2026-11-13T00:00:00+01:00")
    a2 = art("Article de presse", source_id="presse", publie_le="2026-11-14T00:00:00+01:00")
    a3 = art(
        "Circulaire de 2016",
        source_id="bct",
        url="https://x/3",
        publie_le="2016-12-30T00:00:00+01:00",
    )
    a4 = art("Sans date", source_id="bct", url="https://x/4")
    a5 = art("Doublon", source_id="bct", url="https://x/5", groupe=a4.id)
    a4.groupe = a4.id
    assert alertes.eligibles([a1, a2, a3, a4, a5], SOURCES, MAINTENANT) == [a1, a4]


def test_message_d_alerte():
    d = [
        {
            "source": "BCT",
            "titre": "Circulaire <n°2026-09> & suite",
            "url": "https://bct.tn/a?x=1&y=2",
            "langue": "fr",
        },
        {
            "source": "Fitch",
            "titre": "Rating affirmed",
            "url": "https://f.com/a",
            "langue": "en",
            "payant": True,
            "url_traduite": "https://f-com.translate.goog/a?_x_tr_sl=en",
        },
    ]
    m = alertes.construire_message(d)
    assert "<b>BCT</b>" in m and "Circulaire &lt;n°2026-09&gt; &amp; suite" in m
    assert 'href="https://bct.tn/a?x=1&amp;y=2"' in m
    assert "[EN]" in m and "🔒" in m and ">FR</a>" in m
    assert alertes.construire_message(d, differe=True).startswith(
        "Détectées pendant la plage silencieuse"
    )


def test_message_tronque_au_dela_de_la_limite():
    d = [
        {"source": "BCT", "titre": f"Circulaire {i}", "url": f"https://bct.tn/{i}"}
        for i in range(20)
    ]
    m = alertes.construire_message(d)
    assert m.count("<b>BCT</b>") == alertes.MAX_PAR_MESSAGE
    assert "… et 5 autre(s) alerte(s)" in m
