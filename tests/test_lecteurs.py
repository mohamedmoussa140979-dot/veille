"""A1 : lecteurs testés sur des pages réelles enregistrées (aucun accès réseau)."""

from pathlib import Path

import pytest

from veille.collecte.dates import lire_date
from veille.collecte.lecteurs import ErreurLecture, lire

FIX = Path(__file__).parent / "fixtures"


def source(id_, type_, url, **kw):
    base = {
        "id": id_, "nom": id_.upper(), "url": url, "type": type_, "chapitre": "eco-tunisie",
        "langue": "fr", "alerte": False, "payant": False, "actif": True,
    }  # fmt: skip
    return {**base, **kw}


def charger(nom):
    return (FIX / nom).read_bytes()


# --- dates ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "texte, attendu",
    [
        ("10-11-2026", "2026-11-10T00:00:00+01:00"),
        ("12-11-2026 ", "2026-11-12T00:00:00+01:00"),
        ("06/11/2026", "2026-11-06T00:00:00+01:00"),
        ("30/10/2026 16:01", "2026-10-30T16:01:00+01:00"),
        ("2026-10-30T16:01:00+01:00", "2026-10-30T16:01:00+01:00"),
        ("2026-02-02T08:00:00Z", "2026-02-02T09:00:00+01:00"),
        ("Circulaire n°2016-10 du 30\xa0décembre\xa02016", "2016-12-30T00:00:00+01:00"),
        ("le 1er août 2026", "2026-08-01T00:00:00+01:00"),
        ("31/02/2026", None),
        ("pas de date", None),
        (None, None),
    ],
)
def test_lire_date(texte, attendu):
    assert lire_date(texte) == attendu


# --- BCT --------------------------------------------------------------------------------


def test_bct_actualites():
    s = source("bct", "bct", "https://www.bct.gov.tn/bct/siteprod/index.jsp")
    articles = lire(s, charger("bct_index.html"))
    assert len(articles) == 5
    a = articles[0]
    assert a.titre == "Les paiements en chiffres en Tunisie"
    assert a.url == "https://www.bct.gov.tn/bct/siteprod/actualites.jsp?id=1289"
    assert a.publie_le == "2026-11-10T00:00:00+01:00"
    assert len({x.url for x in articles}) == 5  # pas de doublon du carrousel


def test_bct_circulaires_date_lue_dans_le_titre():
    s = source("bct-circ", "bct", "https://www.bct.gov.tn/bct/siteprod/page.jsp?id=226")
    articles = lire(s, charger("bct_circulaires.html"))
    assert len(articles) == 6
    a = articles[0]
    assert a.titre.startswith("Circulaire de la BCT aux intermédiaires agrées n°2016-10")
    assert a.url == "https://www.bct.gov.tn/bct/siteprod/documents/Cir_2016_10_fr.pdf"
    assert a.publie_le == "2016-12-30T00:00:00+01:00"
    note = articles[3]  # lien imbriqué dans un <div>, document en arabe, « 1er février 2018 »
    assert note.url.endswith("Note_2018_03_ar.pdf")
    assert note.langue == "ar" and note.publie_le == "2018-02-01T00:00:00+01:00"
    assert a.langue == "fr"


# --- INS --------------------------------------------------------------------------------


def test_ins_titre_date_resume_lien():
    s = source("ins", "ins", "https://www.ins.tn/communique-de-presse")
    articles = lire(s, charger("ins.html"))
    assert len(articles) == 5
    a = articles[0]
    assert a.titre == "Commerce Extérieur aux prix courants, Octobre 2026"
    assert (
        a.url == "https://www.ins.tn/publication/commerce-exterieur-aux-prix-courants-octobre-2026"
    )
    assert a.publie_le == "2026-11-12T00:00:00+01:00"
    assert a.resume.startswith("Durant les dix premiers mois de l")


# --- CMF --------------------------------------------------------------------------------


def test_cmf_ignore_le_menu_et_lit_la_date_iso():
    s = source("cmf", "cmf", "https://www.cmf.tn/?q=avis-et-d-cisions-du-cmf", alerte=True)
    articles = lire(s, charger("cmf_avis.html"))
    assert len(articles) == 6
    assert all("bulletin-officiel" not in a.url for a in articles)  # raccourcis du menu écartés
    assert articles[0].publie_le == "2026-10-30T16:01:00+01:00"
    assert all(a.url.startswith("https://www.cmf.tn/") for a in articles)


def test_cmf_titre_arabe_detecte():
    s = source("cmf", "cmf", "https://www.cmf.tn/?q=avis-et-d-cisions-du-cmf")
    articles = lire(s, charger("cmf_avis.html"))
    assert articles[0].langue == "ar"
    assert any(a.langue == "fr" for a in articles[1:])


# --- BVMT -------------------------------------------------------------------------------


def test_bvmt_avis_date_de_la_carte_pas_celle_du_titre():
    s = source("bvmt-avis", "bvmt", "https://tunis-stockexchange.com/avis-decisions")
    articles = lire(s, charger("bvmt_avis.html"))
    assert len(articles) == 4
    a = articles[0]
    assert a.titre.startswith("TUNIS RE - Cotation en Bourse des titres")
    assert a.publie_le == "2026-11-06T00:00:00+01:00"
    assert a.url.startswith("https://tunis-stockexchange.com/tunis-re-cotation")


def test_bvmt_publications():
    s = source("bvmt-pub", "bvmt", "https://tunis-stockexchange.com/publications-societes")
    articles = lire(s, charger("bvmt_publications.html"))
    a = articles[0]
    assert a.titre == "TUNISAIR - Indicateurs d'activités trimestriels du 30/09/2026"
    assert a.publie_le == "2026-11-13T00:00:00+01:00"  # date de publication, pas « 30/09/2026 »


# --- RSS et Google News -----------------------------------------------------------------


def test_rss_business_news():
    s = source("bn", "rss", "https://www.businessnews.com.tn/feed")
    articles = lire(s, charger("rss_businessnews.xml"))
    assert len(articles) == 4
    assert all(a.url.startswith("http") and a.titre and a.publie_le for a in articles)
    assert all("<" not in a.resume for a in articles)


def test_rss_le_monde():
    s = source("lm", "rss", "https://www.lemonde.fr/economie/rss_full.xml", langue="fr")
    assert len(lire(s, charger("rss_lemonde.xml"))) == 4


def test_google_news_titre_sans_suffixe_media_et_site_annonce():
    s = source("fitch", "google-news", "https://news.google.com/rss/search?q=Fitch", langue="en")
    articles = lire(s, charger("gnews_fitch.xml"))
    a = articles[0]
    assert a.titre == "Tunisia off Fitch watch list as B-rating confirmed"
    assert a.source == "APAnews - Agence de Presse Africaine"
    assert a.media_url == "https://apanews.net"
    assert a.url.startswith("https://news.google.com/")  # résolu plus tard par l'orchestrateur
    assert a.langue == "en"


# --- HTML générique ---------------------------------------------------------------------


def test_html_generique_garde_les_titres_du_meme_site_seulement():
    s = source("tn", "html-generique", "https://www.tunisienumerique.com/")
    articles = lire(s, charger("html_generique.html"))
    assert len(articles) == 8
    assert all(a.url.startswith("https://www.tunisienumerique.com/") for a in articles)
    assert all(len(a.titre) >= 30 for a in articles)  # menu et liens externes écartés


# --- page qui change --------------------------------------------------------------------


def test_page_sans_aucun_article_est_une_erreur_pas_un_zero():
    s = source("ins", "ins", "https://www.ins.tn/communique-de-presse")
    with pytest.raises(ErreurLecture):
        lire(s, b"<html><body><p>Maintenance</p></body></html>")


def test_flux_html_au_lieu_de_xml_est_une_erreur():
    s = source("wmc", "rss", "https://www.webmanagercenter.com/feed/")
    with pytest.raises(ErreurLecture):
        lire(s, b"<!doctype html><html><head><title>Accueil</title></head><body></body></html>")
