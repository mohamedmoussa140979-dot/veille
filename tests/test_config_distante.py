"""Lecture du document de configuration distant et repli sur les fichiers locaux (sans réseau)."""

import copy

import pytest

from tests.conftest import FausseReponse, FauxClient
from veille.config import charger_parametres, plafond_claude_usd
from veille.config_distante import (
    ConfigDistanteIndisponible,
    charger_configuration,
    minutes,
    valider_document,
)
from veille.http import ErreurReseau
from veille.journal import Journal

JETON = "jeton-de-test-0123456789"
CONTENU_SECRET = "mot-secret-du-document-xyz"

DOCUMENT = {
    "version": 1,
    "genere_le": "2026-11-17T06:00:00Z",
    "sources": [
        {
            "id": "bct-actualites", "nom": "BCT", "url": "https://www.bct.gov.tn/bct/siteprod/index.jsp",
            "type": "bct", "chapitre": "eco-tunisie", "langue": "fr", "alerte": True,
            "payant": False, "actif": True, "filtre": False, "selecteur": None,
        },
        {
            "id": "ancienne", "nom": "Ancienne", "url": "https://exemple.tn/", "type": "rss",
            "chapitre": "eco-tunisie", "langue": "fr", "alerte": False, "payant": False,
            "actif": False, "filtre": True, "selecteur": None,
        },
    ],
    "horaires": {
        "collectes": {"ouvres": ["07:15", "09:15"], "weekend": ["09:15"]},
        "editions": {"matin": "07:30", "soir": "18:30", "weekend": "09:30"},
        "plage_silencieuse": {"debut": "23:00", "fin": "06:30"},
    },
    "ligne_editoriale": {"mots_exclus": {"sport": ["football"], "arts": [CONTENU_SECRET]}},
    "parametres": {"conservation_mois": 12, "plafond_claude_usd_mois": 7.5},
}  # fmt: skip


def doc(**modifs):
    d = copy.deepcopy(DOCUMENT)
    d.update(modifs)
    return d


def charger(scenario, token=JETON):
    journal = Journal(sortie=lambda _t: None)
    journal.enregistrer_secret(JETON)
    client = FauxClient(scenario)
    cfg = charger_configuration(client, charger_parametres(), journal, token=token)
    return cfg, journal, client


def codes(journal):
    return [e["code"] for e in journal.evenements]


def tout_le_journal(journal):
    return str(journal.evenements)


def test_document_valide_remplace_les_fichiers_locaux():
    cfg, journal, client = charger([FausseReponse(200, json_=DOCUMENT)])
    assert cfg.origine == "distante" and cfg.raison_repli is None
    assert [s["id"] for s in cfg.sources] == ["bct-actualites", "ancienne"]
    assert [s["id"] for s in cfg.sources_actives] == ["bct-actualites"]
    assert cfg.regles_filtre["mots_exclus"]["sport"] == ["football"]
    assert cfg.regles_filtre["expressions_conservees"]  # reste local
    assert cfg.plage_silencieuse == (23 * 60, 6 * 60 + 30)
    assert cfg.plafond_claude_usd == 7.5 and cfg.conservation_mois == 12
    assert "config_distante" in codes(journal)


def test_appel_get_avec_jeton_delai_de_10_s_et_url_du_parametre():
    _, _, client = charger([FausseReponse(200, json_=DOCUMENT)])
    appel = client.appels[0]
    assert appel["methode"] == "GET"
    assert appel["url"] == (
        "https://pfm-actualites-recette.abt-mohamed-moussa.workers.dev/veille/config"
    )
    assert appel["headers"]["Authorization"] == f"Bearer {JETON}"
    assert appel["timeout"] == 10.0


def test_sans_jeton_aucun_appel_et_configuration_locale():
    cfg, journal, client = charger([], token="")
    assert cfg.origine == "locale" and cfg.raison_repli is None
    assert client.appels == []
    assert codes(journal) == ["config_locale"]  # information, pas un avertissement de santé
    assert cfg.plage_silencieuse == (22 * 60, 7 * 60)
    assert any(s["actif"] for s in cfg.sources)


@pytest.mark.parametrize(
    "reponse, attendu",
    [
        (FausseReponse(404), "404"),
        (FausseReponse(401), "401"),
        (FausseReponse(500), "HTTP 500"),
        (FausseReponse(503), "HTTP 503"),
        (ErreurReseau("délai"), "injoignable"),
        (FausseReponse(200, texte="pas du json"), "JSON"),
        (FausseReponse(200, json_=doc(version=2)), "version 2 inconnue"),
        (FausseReponse(200, json_=doc(version="1")), "version ? inconnue"),
        (FausseReponse(200, json_={"version": 1}), "document invalide"),
        (FausseReponse(200, json_=[1, 2]), "document invalide"),
    ],
)
def test_repli_sur_les_fichiers_locaux_sans_jamais_lever(reponse, attendu):
    cfg, journal, _ = charger([reponse])
    assert cfg.origine == "locale"
    assert attendu in cfg.raison_repli
    assert "config_distante_repli" in codes(journal)
    assert any(s["actif"] for s in cfg.sources_actives)


def test_ni_le_jeton_ni_le_contenu_ne_sont_journalises():
    invalides = [
        doc(parametres={"conservation_mois": 12, "plafond_claude_usd_mois": CONTENU_SECRET}),
        doc(sources=[{**DOCUMENT["sources"][0], "chapitre": CONTENU_SECRET}]),
        doc(version=CONTENU_SECRET),
    ]
    for invalide in invalides:
        _, journal, _ = charger([FausseReponse(200, json_=invalide)])
        assert "config_distante_repli" in codes(journal)
        assert JETON not in tout_le_journal(journal)
        assert CONTENU_SECRET not in tout_le_journal(journal)
    _, journal, _ = charger([FausseReponse(200, json_=DOCUMENT)])
    assert JETON not in tout_le_journal(journal)
    assert CONTENU_SECRET not in tout_le_journal(journal)  # mots exclus jamais recopiés


def test_source_de_type_inconnu_ignoree_et_signalee_sans_etre_fatale():
    inconnue = {**DOCUMENT["sources"][0], "id": "nouvelle", "type": "atom-2030"}
    cfg, journal, _ = charger(
        [FausseReponse(200, json_=doc(sources=[*DOCUMENT["sources"], inconnue]))]
    )
    assert cfg.origine == "distante"
    assert "nouvelle" not in [s["id"] for s in cfg.sources]
    assert cfg.ignorees == ["nouvelle"]
    avert = [e for e in journal.evenements if e["code"] == "config_source_ignoree"]
    assert len(avert) == 1 and avert[0]["niveau"] == "avertissement"
    assert "atom-2030" not in tout_le_journal(journal)


def test_selecteur_conserve_seulement_pour_html_generique():
    html = {**DOCUMENT["sources"][0], "id": "page", "type": "html-generique", "selecteur": "main a"}
    rss = {**DOCUMENT["sources"][1], "id": "flux", "selecteur": "main a"}
    cfg, _, _ = charger([FausseReponse(200, json_=doc(sources=[html, rss]))])
    par_id = {s["id"]: s for s in cfg.sources}
    assert par_id["page"]["selecteur"] == "main a"
    assert "selecteur" not in par_id["flux"]


def test_identifiants_en_double_refuses():
    d = doc(sources=[DOCUMENT["sources"][0], DOCUMENT["sources"][0]])
    cfg, _, _ = charger([FausseReponse(200, json_=d)])
    assert cfg.origine == "locale" and "en double" in cfg.raison_repli


@pytest.mark.parametrize(
    "modif",
    [
        {"parametres": {"conservation_mois": 0, "plafond_claude_usd_mois": 5}},
        {"parametres": {"conservation_mois": 61, "plafond_claude_usd_mois": 5}},
        {"parametres": {"conservation_mois": 12, "plafond_claude_usd_mois": -1}},
        {"parametres": {"conservation_mois": 12, "plafond_claude_usd_mois": True}},
        {"ligne_editoriale": {"mots_exclus": {"sport": [""]}}},
        {"ligne_editoriale": {"mots_exclus": {"sport": "football"}}},
        {"sources": [{**DOCUMENT["sources"][0], "id": "Majuscule"}]},
        {"sources": [{**DOCUMENT["sources"][0], "url": "ftp://x"}]},
        {"sources": [{**DOCUMENT["sources"][0], "langue": "de"}]},
        {"sources": [{**DOCUMENT["sources"][0], "actif": "oui"}]},
    ],
)
def test_validation_refuse_les_documents_hors_schema(modif):
    with pytest.raises(ConfigDistanteIndisponible):
        valider_document(doc(**modif))


def test_validation_refuse_une_heure_mal_formee():
    d = doc()
    d["horaires"]["plage_silencieuse"]["debut"] = "25:00"
    with pytest.raises(ConfigDistanteIndisponible):
        valider_document(d)


def test_le_document_de_reference_du_contrat_est_valide():
    valider_document(DOCUMENT)


def test_le_plafond_distant_l_emporte_sur_la_variable_du_depot(monkeypatch):
    monkeypatch.setenv("CLAUDE_PLAFOND_USD_MOIS", "3")
    params = charger_parametres()
    assert plafond_claude_usd(params) == 3.0  # local : la variable du dépôt
    cfg, _, _ = charger([FausseReponse(200, json_=DOCUMENT)])
    cfg.appliquer_aux_parametres(params)
    assert plafond_claude_usd(params) == 7.5
    cfg_locale, _, _ = charger([], token="")
    params2 = cfg_locale.appliquer_aux_parametres(charger_parametres())
    assert plafond_claude_usd(params2) == 3.0


def test_minutes():
    assert minutes("07:15") == 435 and minutes("00:00") == 0
