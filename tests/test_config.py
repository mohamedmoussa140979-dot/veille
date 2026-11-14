from pathlib import Path

import pytest

from veille.config import ErreurConfig, charger_exclusions, charger_parametres, charger_sources

RACINE = Path(__file__).resolve().parent.parent


def ecrire(tmp_path, texte):
    f = tmp_path / "sources.yaml"
    f.write_text(texte, encoding="utf-8")
    return f


SOURCE_OK = """
sources:
  - id: bct-actualites
    nom: BCT
    url: https://www.bct.gov.tn/bct/siteprod/index.jsp
    type: bct
    chapitre: eco-tunisie
    langue: fr
    alerte: true
    payant: false
    actif: true
"""


def test_les_fichiers_du_depot_sont_valides():
    assert charger_sources(RACINE / "config" / "sources.yaml") == []
    assert charger_exclusions(RACINE / "config" / "exclusions.yaml") == []
    p = charger_parametres(RACINE / "config" / "parametres.yaml")
    assert p["claude"]["plafond_usd_mois"] == 5.0
    assert p["claude"]["modele"].startswith("claude-")


def test_source_valide(tmp_path):
    sources = charger_sources(ecrire(tmp_path, SOURCE_OK))
    assert sources[0]["id"] == "bct-actualites" and sources[0]["alerte"] is True


def test_type_inconnu_refuse(tmp_path):
    with pytest.raises(ErreurConfig, match="type"):
        charger_sources(ecrire(tmp_path, SOURCE_OK.replace("type: bct", "type: wordpress")))


def test_champ_manquant_refuse(tmp_path):
    with pytest.raises(ErreurConfig, match="payant"):
        charger_sources(ecrire(tmp_path, SOURCE_OK.replace("    payant: false\n", "")))


def test_identifiants_en_double_refuses(tmp_path):
    doublon = SOURCE_OK + SOURCE_OK.split("sources:")[1]
    with pytest.raises(ErreurConfig, match="en double"):
        charger_sources(ecrire(tmp_path, doublon))


def test_variable_d_environnement_surcharge_le_plafond(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PLAFOND_USD_MOIS", "12.5")
    p = charger_parametres(RACINE / "config" / "parametres.yaml")
    assert p["claude"]["plafond_usd_mois"] == 12.5


def test_plafond_non_numerique_refuse(monkeypatch):
    monkeypatch.setenv("CLAUDE_PLAFOND_USD_MOIS", "beaucoup")
    with pytest.raises(ErreurConfig, match="CLAUDE_PLAFOND_USD_MOIS"):
        charger_parametres(RACINE / "config" / "parametres.yaml")
