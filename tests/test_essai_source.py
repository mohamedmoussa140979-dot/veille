"""Mode test d'une source (bouton « Tester » du back-office), sans réseau."""

from pathlib import Path

import pytest

from tests.conftest import FausseReponse, FauxClient
from veille.collecte import __main__ as collecte_cli
from veille.collecte import essai_source
from veille.config import charger_parametres
from veille.config_distante import Configuration, charger_locale
from veille.etat import EtatGit
from veille.http import ErreurReseau
from veille.journal import Journal

FIX = Path(__file__).parent / "fixtures"
JETON = "jeton-config-de-test-0123"
URL_RESULTAT = "https://pfm-actualites-recette.abt-mohamed-moussa.workers.dev/veille/resultat-test"


def journal():
    j = Journal(sortie=lambda _t: None)
    j.enregistrer_secret(JETON)
    return j


def config(**modifs):
    c = charger_locale(charger_parametres())
    for cle, valeur in modifs.items():
        setattr(c, cle, valeur)
    return c


def page_bct():
    return FausseReponse(200, contenu=(FIX / "bct_index.html").read_bytes())


def source_html(sid="page", **kw):
    return {
        "id": sid, "nom": "Page", "url": "https://exemple.tn/", "type": "html-generique",
        "chapitre": "eco-tunisie", "langue": "fr", "alerte": False, "payant": False,
        "actif": True, **kw,
    }  # fmt: skip


def page_de_liens(n, longueur=60):
    liens = "".join(
        f'<a href="/article-{i}">{"Titre numéro " + str(i) + " " + "x" * longueur}</a>'
        for i in range(n)
    )
    return FausseReponse(200, contenu=f"<html><body>{liens}</body></html>".encode())


def test_source_lue_resultat_borne_et_envoye_au_worker(monkeypatch):
    monkeypatch.setenv("VEILLE_CONFIG_TOKEN", JETON)
    client = FauxClient([page_bct(), FausseReponse(200, json_={"ok": True})])
    j = journal()
    code = essai_source.lancer(
        "bct-actualites", "dem-123", config(), client, j, charger_parametres()
    )
    assert code == 0
    lecture, envoi = client.appels
    assert lecture["methode"] == "GET" and "bct.gov.tn" in lecture["url"]
    assert envoi["methode"] == "POST" and envoi["url"] == URL_RESULTAT
    assert envoi["headers"]["Authorization"] == f"Bearer {JETON}"
    corps = envoi["json"]
    assert corps["demande_id"] == "dem-123" and corps["source_id"] == "bct-actualites"
    assert corps["ok"] is True and corps["erreur"] is None
    assert 1 <= len(corps["articles"]) <= 30
    for a in corps["articles"]:
        assert set(a) == {"titre", "url", "publie_le"}  # jamais de texte d'article
        assert len(a["titre"]) <= 200 and a["url"].startswith("https://")
    assert JETON not in str(j.evenements)


def test_au_plus_trente_articles_et_titres_tronques():
    c = config(sources=[source_html()])
    client = FauxClient([page_de_liens(45, longueur=400)])
    r = essai_source.executer("page", c, client, journal())
    assert r["ok"] and len(r["articles"]) == 30
    assert all(len(a["titre"]) <= 200 for a in r["articles"])


def test_titre_de_plus_de_200_caracteres_est_tronque_par_le_test_lui_meme(monkeypatch):
    from veille.collecte.article import Article

    long = Article(
        source_id="page", source="Page", titre="T" * 500, url="https://exemple.tn/a?utm_x=1"
    )
    monkeypatch.setattr(essai_source, "_recolter", lambda *a, **k: [long])
    r = essai_source.executer("page", config(sources=[source_html()]), FauxClient([]), journal())
    assert len(r["articles"][0]["titre"]) == 200
    assert r["articles"][0]["url"] == "https://exemple.tn/a"  # suivi retiré
    assert r["articles"][0]["publie_le"] is None


@pytest.mark.parametrize(
    "source_id, modifs, attendu",
    [
        ("absente", {}, "inconnue"),
        ("Pas Valide!", {}, "invalide"),
        ("", {}, "invalide"),
        ("page", {"sources": [source_html(actif=False)]}, "inactive"),
        ("nouvelle", {"ignorees": ["nouvelle"]}, "type"),
    ],
)
def test_source_inconnue_inactive_ou_invalide_donne_ok_false_lisible(source_id, modifs, attendu):
    client = FauxClient([])
    r = essai_source.executer(source_id, config(**modifs), client, journal())
    assert r["ok"] is False and r["articles"] == [] and attendu in r["erreur"]
    assert client.appels == []  # rien n'est lu


def test_source_inconnue_mentionne_le_repli_local():
    c = config(raison_repli="HTTP 404 : route absente")
    r = essai_source.executer("absente", c, FauxClient([]), journal())
    assert "configuration locale utilisée" in r["erreur"] and "404" in r["erreur"]


@pytest.mark.parametrize(
    "reponse, attendu",
    [
        (FausseReponse(403), "HTTP 403"),
        (ErreurReseau("coupé"), "coupé"),
        (
            FausseReponse(200, contenu=b"<html><body><p>Maintenance</p></body></html>"),
            "aucun article",
        ),
    ],
)
def test_source_en_panne_ok_false_avec_cause(reponse, attendu):
    c = config(sources=[source_html()])
    r = essai_source.executer("page", c, FauxClient([reponse]), journal())
    assert r["ok"] is False and attendu in r["erreur"] and len(r["erreur"]) <= 300


def test_le_resultat_d_echec_est_aussi_envoye(monkeypatch):
    monkeypatch.setenv("VEILLE_CONFIG_TOKEN", JETON)
    client = FauxClient([FausseReponse(200, json_={})])
    code = essai_source.lancer("absente", "d1", config(), client, journal(), charger_parametres())
    assert code == 0 and client.appels[0]["json"]["ok"] is False
    assert client.appels[0]["json"]["erreur"]


def test_sans_jeton_une_demande_reelle_echoue_et_un_essai_local_n_envoie_rien(monkeypatch):
    monkeypatch.delenv("VEILLE_CONFIG_TOKEN", raising=False)
    client = FauxClient([page_bct()])
    assert (
        essai_source.lancer(
            "bct-actualites", "d1", config(), client, journal(), charger_parametres()
        )
        == 1
    )
    assert [a["methode"] for a in client.appels] == ["GET"]  # pas de POST
    client = FauxClient([page_bct()])
    assert (
        essai_source.lancer(
            "bct-actualites", None, config(), client, journal(), charger_parametres()
        )
        == 0
    )
    assert [a["methode"] for a in client.appels] == ["GET"]


def test_demande_id_invalide_n_est_pas_envoyee(monkeypatch):
    monkeypatch.setenv("VEILLE_CONFIG_TOKEN", JETON)
    client = FauxClient([page_bct()])
    code = essai_source.lancer(
        "bct-actualites", "x; rm -rf /", config(), client, journal(), charger_parametres()
    )
    assert code == 1 and [a["methode"] for a in client.appels] == ["GET"]


@pytest.mark.parametrize("reponse", [FausseReponse(500), FausseReponse(401), ErreurReseau("coupé")])
def test_echec_d_envoi_du_resultat_code_1_sans_jeton_au_journal(monkeypatch, reponse):
    monkeypatch.setenv("VEILLE_CONFIG_TOKEN", JETON)
    client, j = FauxClient([page_bct(), reponse]), journal()
    assert (
        essai_source.lancer("bct-actualites", "d1", config(), client, j, charger_parametres()) == 1
    )
    assert [e["code"] for e in j.evenements if e["niveau"] == "erreur"] == [
        "test_source_non_envoye"
    ]
    assert JETON not in str(j.evenements)


# --- point d'entrée : aucune alerte, aucun état ---------------------------------------------


def _interdire_etat_et_telegram(monkeypatch):
    def interdit(*a, **k):
        raise AssertionError("le mode test ne touche ni à l'état ni à Telegram")

    monkeypatch.setattr(EtatGit, "depuis_environnement", classmethod(interdit))
    monkeypatch.setattr(collecte_cli, "EtatLocal", interdit)
    monkeypatch.setattr(collecte_cli, "collecter", interdit)
    monkeypatch.setattr(collecte_cli, "envoyer", interdit)
    monkeypatch.setattr("veille.collecte.orchestrateur.envoyer_telegram", interdit)
    monkeypatch.setenv("TG_TOKEN_VEILLE", "jeton-telegram-factice")
    monkeypatch.setenv("TG_CHAT_ID", "1")


def test_main_mode_test_avec_options(monkeypatch):
    _interdire_etat_et_telegram(monkeypatch)
    monkeypatch.setenv("VEILLE_CONFIG_TOKEN", JETON)
    # config distante (1er appel), lecture de la source (2e), résultat (3e)
    from tests.test_config_distante import DOCUMENT

    client = FauxClient(
        [FausseReponse(200, json_=DOCUMENT), page_bct(), FausseReponse(200, json_={"ok": True})]
    )
    monkeypatch.setattr(collecte_cli, "Client", lambda **kw: client)
    assert collecte_cli.main(["--source-test", "bct-actualites", "--demande-id", "dem-9"]) == 0
    assert [a["methode"] for a in client.appels] == ["GET", "GET", "POST"]
    assert client.appels[2]["json"]["demande_id"] == "dem-9"


def test_main_mode_test_par_variables_d_environnement(monkeypatch):
    _interdire_etat_et_telegram(monkeypatch)
    monkeypatch.delenv("VEILLE_CONFIG_TOKEN", raising=False)  # config locale, pas d'envoi
    monkeypatch.setenv("SOURCE_TEST", "bct-actualites")
    monkeypatch.setenv("DEMANDE_ID", "dem-10")
    client = FauxClient([page_bct()])
    monkeypatch.setattr(collecte_cli, "Client", lambda **kw: client)
    assert collecte_cli.main([]) == 1  # demande réelle mais pas de jeton : échec visible
    assert [a["methode"] for a in client.appels] == ["GET"]


def test_main_sans_mode_test_n_est_pas_affecte(monkeypatch):
    monkeypatch.delenv("SOURCE_TEST", raising=False)
    monkeypatch.setenv("SOURCE_TEST", "")  # entrée de workflow vide
    assert collecte_cli.option(["--source-test"], "--source-test") is None
    assert isinstance(config(), Configuration)
