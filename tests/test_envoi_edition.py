"""Envoi des éditions vers Mizeniti (POST /actualites/ingest), sans réseau."""

import json

import pytest

from tests.conftest import FausseReponse, FauxClient
from tests.test_edition import CLASSEMENT_OK, redaction
from tests.test_edition_cli import avec_ia, env  # noqa: F401 - `env` est une fixture
from veille.config import charger_parametres
from veille.edition import __main__ as cli
from veille.edition.envoi import envoyer_edition
from veille.http import ErreurReseau
from veille.journal import Journal

JETON = "jeton-ingest-de-test-0123"
CORPS = '{"version": 1, "id": "2026-11-17-matin", "texte": "contenu-confidentiel-xyz"}\n'
URL = "https://pfm-actualites-recette.abt-mohamed-moussa.workers.dev/actualites/ingest"


def nouveau_journal():
    j = Journal(sortie=lambda _t: None)
    j.enregistrer_secret(JETON)
    return j


def tout(journal):
    return str(journal.evenements)


def test_sans_jeton_l_envoi_est_saute_sans_appel(monkeypatch):
    monkeypatch.delenv("MIZENITI_INGEST_TOKEN", raising=False)
    client, journal = FauxClient([]), nouveau_journal()
    assert (
        envoyer_edition(client, charger_parametres(), CORPS, "2026-11-17-matin", journal) == "saute"
    )
    assert client.appels == []
    assert [e["code"] for e in journal.evenements] == ["ingest_saute"]
    assert journal.evenements[0]["niveau"] == "info"


def test_envoi_nominal_url_jeton_et_corps_exact(monkeypatch):
    monkeypatch.setenv("MIZENITI_INGEST_TOKEN", JETON)
    client, journal = FauxClient([FausseReponse(200, json_={"ok": True})]), nouveau_journal()
    assert (
        envoyer_edition(client, charger_parametres(), CORPS, "2026-11-17-matin", journal)
        == "envoye"
    )
    appel = client.appels[0]
    assert appel["methode"] == "POST" and appel["url"] == URL
    assert appel["data"] == CORPS.encode("utf-8")
    assert appel["headers"]["Authorization"] == f"Bearer {JETON}"
    assert appel["headers"]["Content-Type"].startswith("application/json")
    assert JETON not in tout(journal) and "contenu-confidentiel" not in tout(journal)


@pytest.mark.parametrize(
    "reponse, raison",
    [
        (FausseReponse(401, texte="contenu-confidentiel-xyz"), "HTTP 401"),
        (FausseReponse(400, texte="contenu-confidentiel-xyz"), "HTTP 400"),
        (FausseReponse(500), "HTTP 500"),
        (FausseReponse(503), "HTTP 503"),
        (ErreurReseau(f"POST hote : Timeout {JETON} contenu-confidentiel-xyz"), "injoignable"),
        (ValueError("bizarre"), "inattendue"),
    ],
)
def test_un_echec_est_signale_sans_lever_ni_journaliser_corps_ou_jeton(
    monkeypatch, reponse, raison
):
    monkeypatch.setenv("MIZENITI_INGEST_TOKEN", JETON)
    client, journal = FauxClient([reponse]), nouveau_journal()
    assert (
        envoyer_edition(client, charger_parametres(), CORPS, "2026-11-17-matin", journal) == "echec"
    )
    echec = [e for e in journal.evenements if e["code"] == "ingest_echec"]
    assert len(echec) == 1 and echec[0]["niveau"] == "erreur"
    assert raison in echec[0]["ctx"]["raison"]
    assert JETON not in tout(journal) and "contenu-confidentiel" not in tout(journal)


def test_adresse_du_worker_absente_est_un_echec_signale(monkeypatch):
    monkeypatch.setenv("MIZENITI_INGEST_TOKEN", JETON)
    params = charger_parametres()
    del params["mizeniti"]
    client, journal = FauxClient([]), nouveau_journal()
    assert envoyer_edition(client, params, CORPS, "x", journal) == "echec"
    assert client.appels == []


# --- de bout en bout dans le point d'entrée de l'édition ---------------------------------


def _client_faux(monkeypatch, scenario):
    faux = FauxClient(scenario)
    monkeypatch.setattr(cli, "Client", lambda **kw: faux)
    return faux


def test_edition_envoyee_a_mizeniti_avec_le_fichier_ecrit(env, monkeypatch):  # noqa: F811
    etat, envoyes, mp = env
    mp.setenv("MIZENITI_INGEST_TOKEN", JETON)
    mp.delenv("VEILLE_CONFIG_TOKEN", raising=False)
    faux = _client_faux(mp, [FausseReponse(200, json_={"ok": True})])
    avec_ia(mp, CLASSEMENT_OK, redaction())
    assert cli.main(["--type", "matin", "--heures", "24"]) == 0
    assert len(faux.appels) == 1 and faux.appels[0]["url"] == URL
    fichier = etat.lire("editions/2026-11-17-matin.json")
    assert faux.appels[0]["data"] == fichier.encode("utf-8")
    assert len(envoyes) == 1  # Telegram aussi


@pytest.mark.parametrize(
    "scenario", [[FausseReponse(500)], [FausseReponse(401)], [ErreurReseau("coupé")]]
)
def test_echec_d_envoi_n_empeche_ni_telegram_ni_l_edition_et_remonte_a_la_sante(
    env,  # noqa: F811
    monkeypatch,
    scenario,
):
    etat, envoyes, mp = env
    mp.setenv("MIZENITI_INGEST_TOKEN", JETON)
    mp.delenv("VEILLE_CONFIG_TOKEN", raising=False)
    _client_faux(mp, scenario)
    avec_ia(mp, CLASSEMENT_OK, redaction())
    assert cli.main(["--type", "matin", "--heures", "24"]) == 0  # le job reste vert : Pages suit
    assert etat.lire("editions/2026-11-17-matin.json") is not None
    assert len(envoyes) == 1 and envoyes[0][0] == "matin"
    evenements = [
        json.loads(ligne)
        for fichier in etat.lister("sante")
        for ligne in etat.lire(fichier).splitlines()
    ]
    echec = [e for e in evenements if e["code"] == "ingest_echec"]
    assert len(echec) == 1 and JETON not in str(evenements)


def test_sans_jeton_d_ingestion_l_edition_se_fait_sans_appel(env, monkeypatch):  # noqa: F811
    etat, envoyes, mp = env
    mp.delenv("MIZENITI_INGEST_TOKEN", raising=False)
    mp.delenv("VEILLE_CONFIG_TOKEN", raising=False)
    faux = _client_faux(mp, [])
    avec_ia(mp, CLASSEMENT_OK, redaction())
    assert cli.main(["--type", "matin", "--heures", "24"]) == 0
    assert faux.appels == [] and len(envoyes) == 1
