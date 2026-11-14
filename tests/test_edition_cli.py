"""Points d'entrée `veille.edition` et `veille.edition.site` de bout en bout (IA et Telegram simulés)."""

import json
from datetime import UTC, datetime

import pytest

from tests.test_edition import ARTICLES, CLASSEMENT_OK, FauxIa, redaction
from veille.edition import __main__ as cli
from veille.edition import site
from veille.edition.fenetre import type_depuis_cron
from veille.etat import EtatGit, EtatLocal
from veille.ia import ErreurIa, Ia

MAINTENANT = datetime(2026, 11, 17, 6, 30, tzinfo=UTC)


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Cwd isolé, état local à la place de la branche data, Telegram enregistré, heure figée."""
    monkeypatch.chdir(tmp_path)
    etat = EtatLocal(tmp_path / "etat")
    monkeypatch.setattr(EtatGit, "depuis_environnement", classmethod(lambda cls, *a, **k: etat))
    envoyes = []
    monkeypatch.setattr(cli, "envoyer", lambda type_, corps, **kw: envoyes.append((type_, corps)))
    monkeypatch.setattr("veille.temps.maintenant", lambda: MAINTENANT)
    monkeypatch.setenv("TG_TOKEN_VEILLE", "jeton-de-test")
    monkeypatch.setenv("TG_CHAT_ID", "42")
    monkeypatch.setenv("GITHUB_REPOSITORY", "Proprietaire/veille")
    monkeypatch.delenv("EDITION_SCHEDULE", raising=False)
    monkeypatch.setattr(cli, "donnees_marches", lambda *a, **k: None)  # pas de réseau en test
    lignes = [json.dumps(a | {"vu_le": "2026-11-17T05:00:00+01:00"}) for a in ARTICLES]
    etat.ajouter_lignes("articles/2026-11-17.jsonl", lignes)
    return etat, envoyes, monkeypatch


def avec_ia(monkeypatch, *reponses):
    ia = FauxIa(*reponses)
    monkeypatch.setattr(Ia, "depuis_environnement", classmethod(lambda cls, *a, **k: ia))
    return ia


def test_edition_nominale_ecrite_sur_data_et_envoyee_sur_telegram(env):
    etat, envoyes, mp = env
    avec_ia(mp, CLASSEMENT_OK, redaction())
    assert cli.main(["--type", "matin", "--heures", "24"]) == 0
    edition = json.loads(etat.lire("editions/2026-11-17-matin.json"))
    assert edition["id"] == "2026-11-17-matin" and edition["essentiel"]
    historique = etat.lire_json("state/editions.json")
    assert [h["id"] for h in historique] == ["2026-11-17-matin"]
    assert len(envoyes) == 1 and envoyes[0][0] == "matin"
    assert "https://proprietaire.github.io/veille/editions/2026-11-17-matin.html" in envoyes[0][1]


def test_relancer_l_edition_remplace_sans_doublon_d_historique(env):
    etat, envoyes, mp = env
    avec_ia(mp, CLASSEMENT_OK, redaction())
    cli.main(["--type", "matin", "--heures", "24"])
    avec_ia(mp, CLASSEMENT_OK, redaction())
    cli.main(["--type", "matin", "--heures", "24"])
    assert [h["id"] for h in etat.lire_json("state/editions.json")] == ["2026-11-17-matin"]


def test_ia_en_echec_pas_d_edition_et_alerte_sante(env):
    etat, envoyes, mp = env

    class IaHS:
        def generer_json(self, *a, **k):
            raise ErreurIa("Gemini indisponible ; plafond Claude du mois atteint")

    mp.setattr(Ia, "depuis_environnement", classmethod(lambda cls, *a, **k: IaHS()))
    assert cli.main(["--type", "matin", "--heures", "24"]) == 1
    assert etat.lire("editions/2026-11-17-matin.json") is None
    assert envoyes[0][0] == "sante" and "non générée" in envoyes[0][1]


def test_fenetre_vide_message_court_sans_edition(env):
    etat, envoyes, mp = env
    avec_ia(mp)
    assert cli.main(["--type", "soir", "--heures", "0.001"]) == 0
    assert etat.lire("editions/2026-11-17-soir.json") is None
    assert envoyes[0][0] == "soir" and "Aucune actualité" in envoyes[0][1]


def test_le_type_vient_de_l_horaire_du_workflow(env):
    etat, envoyes, mp = env
    mp.setenv("EDITION_SCHEDULE", "30 17 * * 1-5")
    avec_ia(mp, CLASSEMENT_OK, redaction())
    assert cli.main(["--heures", "24"]) == 0
    assert etat.lire("editions/2026-11-17-soir.json") is not None
    assert type_depuis_cron("30 8 * * 0,6") == "weekend" and type_depuis_cron("0 0 * * *") is None


def test_une_edition_invalide_n_arrete_pas_l_archive(tmp_path, capsys):
    data = tmp_path / "data"
    (data / "editions").mkdir(parents=True)
    (data / "editions" / "2026-11-17-matin.json").write_text("{pas du json", encoding="utf-8")
    from tests.test_edition import produire

    (data / "editions" / "2026-11-16-soir.json").write_text(
        json.dumps(produire()[0]), encoding="utf-8"
    )
    assert site.main([str(data), str(tmp_path / "site")]) == 0
    sortie = capsys.readouterr().out
    assert "IGNORÉE 2026-11-17-matin.json" in sortie and "1 édition(s)" in sortie
    assert (tmp_path / "site" / "index.html").exists()
