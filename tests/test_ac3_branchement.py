"""Branchement de la configuration pilotée (AC3) dans la collecte, l'IA et le contrôle de santé."""

from datetime import UTC, datetime

import pytest

from tests.conftest import FausseReponse, FauxClient
from tests.test_config_distante import DOCUMENT, JETON
from veille.collecte import __main__ as collecte_cli
from veille.collecte import alertes
from veille.collecte.article import Article
from veille.collecte.lecteurs import ErreurLecture, lire
from veille.config import charger_parametres, plafond_claude_usd
from veille.config_distante import charger_locale, minutes
from veille.sante import controle


def h(heure_utc, minute=0):
    return datetime(2026, 11, 14, heure_utc, minute, tzinfo=UTC)  # Tunis = UTC + 1


# --- plage silencieuse pilotée -----------------------------------------------------------


def test_plage_par_defaut_inchangee():
    assert alertes.en_plage_silencieuse(h(21, 0))
    assert not alertes.en_plage_silencieuse(h(6, 0))


def test_plage_distante_avec_minutes_et_passage_de_minuit():
    plage = (minutes("23:00"), minutes("06:30"))
    assert alertes.en_plage_silencieuse(h(22, 0), plage)  # 23:00 à Tunis
    assert alertes.en_plage_silencieuse(h(5, 29), plage)  # 06:29
    assert not alertes.en_plage_silencieuse(h(5, 30), plage)  # 06:30
    assert not alertes.en_plage_silencieuse(h(21, 59), plage)  # 22:59


def test_plage_dans_la_meme_journee_et_plage_vide():
    jour = (minutes("13:00"), minutes("15:00"))
    assert alertes.en_plage_silencieuse(h(12, 0), jour)  # 13:00
    assert not alertes.en_plage_silencieuse(h(14, 0), jour)  # 15:00
    assert not alertes.en_plage_silencieuse(h(12, 0), (minutes("07:00"), minutes("07:00")))


def test_message_differe_affiche_la_plage_pilotee():
    exemple = [{"source": "BCT", "titre": "t", "url": "https://x.tn/", "langue": "fr"}]
    assert "(22:00–07:00)" in alertes.construire_message(exemple, differe=True)
    plage = (minutes("23:00"), minutes("06:30"))
    assert "(23:00–06:30)" in alertes.construire_message(exemple, differe=True, plage=plage)


# --- sélecteur CSS (html-generique) ------------------------------------------------------

PAGE = """<html><body>
<nav><a href="/menu-un-lien-de-navigation-assez-long-pour-passer">Un lien de navigation assez long pour passer</a></nav>
<main class="une"><a href="/article-un">Premier article de la zone choisie par le sélecteur</a>
<div><a href="/article-deux">Deuxième article de la zone choisie par le sélecteur</a></div></main>
</body></html>""".encode()


def source_html(**kw):
    return {
        "id": "page", "nom": "Page", "url": "https://exemple.tn/", "type": "html-generique",
        "chapitre": "eco-tunisie", "langue": "fr", "alerte": False, "payant": False,
        "actif": True, **kw,
    }  # fmt: skip


def test_selecteur_limite_la_lecture_a_la_zone():
    sans = lire(source_html(), PAGE)
    avec = lire(source_html(selecteur="main.une"), PAGE)
    assert len(sans) == 3 and len(avec) == 2
    assert all("/article-" in a.url for a in avec)


def test_selecteur_qui_ne_trouve_rien_ou_invalide_est_une_erreur_de_lecture():
    with pytest.raises(ErreurLecture):
        lire(source_html(selecteur="section.absente"), PAGE)
    with pytest.raises(ErreurLecture, match="sélecteur"):
        lire(source_html(selecteur="main[["), PAGE)


# --- contrôle de santé -------------------------------------------------------------------


def ev(code, **ctx):
    return {"t": "2026-11-17T20:00:00+01:00", "niveau": "avertissement", "code": code, "ctx": ctx}


def test_sante_un_seul_repli_n_alerte_pas_deux_oui():
    assert controle.controle_pilotage([ev("config_distante_repli", raison="HTTP 503")]) == []
    a = controle.controle_pilotage([ev("config_distante_repli", raison="HTTP 503")] * 2)
    assert [x.code for x in a] == ["config_distante_repli"]
    assert "HTTP 503" in a[0].texte and "VEILLE_CONFIG_TOKEN" in a[0].action


def test_sante_edition_non_envoyee_alerte_des_la_premiere():
    a = controle.controle_pilotage([ev("ingest_echec", raison="HTTP 401")])
    assert [x.code for x in a] == ["ingest_echec"]
    assert "HTTP 401" in a[0].texte and "MIZENITI_INGEST_TOKEN" in a[0].action


def test_sante_source_ignoree_et_rien_a_signaler():
    a = controle.controle_pilotage([ev("config_source_ignoree", source="nouvelle")])
    assert [x.code for x in a] == ["config_source_ignoree"] and "nouvelle" in a[0].texte
    assert (
        controle.controle_pilotage([{"t": "x", "niveau": "info", "code": "autre", "ctx": {}}]) == []
    )


# --- point d'entrée de la collecte ----------------------------------------------------------


def test_la_collecte_utilise_sources_actives_mots_exclus_et_plage_du_document(monkeypatch):
    vu = {}

    def faux_collecter(**kw):
        vu.update(kw)
        from veille.collecte.orchestrateur import Rapport

        return Rapport(sources_ok=1)

    monkeypatch.setattr(collecte_cli, "collecter", faux_collecter)
    monkeypatch.setattr(collecte_cli, "EtatLocal", lambda *_: object())
    monkeypatch.setenv("VEILLE_CONFIG_TOKEN", JETON)
    monkeypatch.setattr(
        "veille.collecte.__main__.Client",
        lambda **kw: FauxClient([FausseReponse(200, json_=DOCUMENT)]),
    )
    assert collecte_cli.main(["--a-blanc"]) == 0
    assert [s["id"] for s in vu["sources"]] == ["bct-actualites"]  # « ancienne » est inactive
    assert vu["plage_silencieuse"] == (minutes("23:00"), minutes("06:30"))
    foot = Article(
        source_id="x", source="X", titre="Football : le match de samedi", url="https://a.tn/1"
    )
    tennis = Article(
        source_id="x", source="X", titre="Tennis : la finale de dimanche", url="https://a.tn/2"
    )
    assert vu["filtre"].motif_rejet(foot, {}) is not None  # « football » : mot du document
    assert vu["filtre"].motif_rejet(tennis, {}) is None  # « tennis » : mot local, remplacé


def test_la_collecte_sans_jeton_reste_sur_les_fichiers_locaux(monkeypatch):
    vu = {}

    def faux_collecter(**kw):
        vu.update(kw)
        from veille.collecte.orchestrateur import Rapport

        return Rapport(sources_ok=1)

    monkeypatch.setattr(collecte_cli, "collecter", faux_collecter)
    monkeypatch.setattr(collecte_cli, "EtatLocal", lambda *_: object())
    monkeypatch.delenv("VEILLE_CONFIG_TOKEN", raising=False)
    assert collecte_cli.main(["--a-blanc"]) == 0
    assert len(vu["sources"]) == len(charger_locale(charger_parametres()).sources_actives)
    assert vu["plage_silencieuse"] == (22 * 60, 7 * 60)


def test_plafond_local_sans_document(monkeypatch):
    monkeypatch.delenv("CLAUDE_PLAFOND_USD_MOIS", raising=False)
    assert plafond_claude_usd(charger_parametres()) == 5.0
