"""Workflows du pilotage (AC3) : entrées, secrets par l'environnement, crons inchangés."""

from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"


def charger(nom):
    d = yaml.safe_load((WORKFLOWS / f"{nom}.yml").read_text(encoding="utf-8"))
    d["on"] = d.pop(True, d.get("on"))  # YAML lit « on » comme un booléen
    return d


def etapes(d, travail):
    return d["jobs"][travail]["steps"]


def test_collecte_accepte_source_test_et_demande_id_sans_cron_modifie():
    d = charger("collecte")
    entrees = d["on"]["workflow_dispatch"]["inputs"]
    assert {"essai_alerte", "source_test", "demande_id"} <= set(entrees)
    assert entrees["source_test"]["default"] == "" and entrees["demande_id"]["default"] == ""
    # les crons de la spec § 5 : aucun n'a été retiré ni changé par l'AC3
    assert [c["cron"] for c in d["on"]["schedule"]] == [
        "15 6,8,10,12,14,16,19 * * 1-5",
        "15 8,17 * * 0,6",
    ]


def test_collecte_entrees_par_l_environnement_et_secret_de_configuration():
    etape = etapes(charger("collecte"), "collecte")[-1]
    assert etape["env"]["VEILLE_CONFIG_TOKEN"] == "${{ secrets.VEILLE_CONFIG_TOKEN }}"
    assert etape["env"]["SOURCE_TEST"] == "${{ inputs.source_test }}"
    assert etape["env"]["DEMANDE_ID"] == "${{ inputs.demande_id }}"
    # jamais recopiées dans la commande (injection de shell)
    assert "source_test" not in etape["run"] and "demande_id" not in etape["run"]


def test_un_essai_de_source_a_son_propre_groupe_de_concurrence():
    groupe = charger("collecte")["concurrency"]["group"]
    assert "veille-collecte-test-" in groupe and "'veille-collecte'" in groupe


def test_edition_recoit_les_deux_jetons_et_garde_ses_crons():
    d = charger("edition")
    env = etapes(d, "edition")[-1]["env"]
    assert env["MIZENITI_INGEST_TOKEN"] == "${{ secrets.MIZENITI_INGEST_TOKEN }}"
    assert env["VEILLE_CONFIG_TOKEN"] == "${{ secrets.VEILLE_CONFIG_TOKEN }}"
    assert [c["cron"] for c in d["on"]["schedule"]] == [
        "30 6 * * 1-5",
        "30 17 * * 1-5",
        "30 8 * * 0,6",
    ]
    assert d["on"]["workflow_dispatch"]["inputs"]["type"]["options"] == [
        "auto",
        "matin",
        "soir",
        "weekend",
    ]


def test_sante_lit_la_meme_configuration_et_garde_son_cron():
    d = charger("sante")
    assert etapes(d, "sante")[-1]["env"]["VEILLE_CONFIG_TOKEN"].startswith("${{ secrets.")
    assert [c["cron"] for c in d["on"]["schedule"]] == ["0 20 * * *"]
