"""Point d'entrée des points 📈 : horaires, nouvel essai de 18:20, jours sans séance."""

from datetime import UTC, datetime

import pytest

from tests.test_marches import bourse, taux, yahoo_complet
from veille.etat import EtatGit, EtatLocal
from veille.marches import __main__ as cli

VENDREDI_1720 = datetime(2026, 11, 13, 16, 20, tzinfo=UTC)  # séance du 13/11 déjà publiée
LUNDI_1720 = datetime(2026, 11, 16, 16, 20, tzinfo=UTC)  # séance du 16/11 pas encore publiée


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    etat = EtatLocal(tmp_path / "etat")
    monkeypatch.setattr(EtatGit, "depuis_environnement", classmethod(lambda cls, *a, **k: etat))
    envoyes = []
    monkeypatch.setattr(cli, "envoyer", lambda type_, corps, **kw: envoyes.append((type_, corps)))
    monkeypatch.setattr(cli.mizeniti, "charger", lambda *a, **k: (bourse(), taux()))
    monkeypatch.setattr(cli.yahoo, "lire_internationaux", lambda *a, **k: yahoo_complet())
    monkeypatch.setenv("TG_TOKEN_VEILLE", "jeton-de-test")
    monkeypatch.setenv("TG_CHAT_ID", "42")
    monkeypatch.delenv("MARCHES_SCHEDULE", raising=False)

    def heure(instant):
        monkeypatch.setattr("veille.temps.maintenant", lambda: instant)

    heure(VENDREDI_1720)
    return etat, envoyes, monkeypatch, heure


def test_point_bourse_de_la_seance_du_jour(env):
    etat, envoyes, _, _ = env
    assert cli.main(["--point", "bourse", "--essai", "1"]) == 0
    assert len(envoyes) == 1 and envoyes[0][0] == "marches"
    assert "séance du 13/11/2026" in envoyes[0][1] and "TUNINDEX" in envoyes[0][1]
    assert etat.lire_json("state/marches.json")["bourse_envoye"] == "2026-11-13"
    # un second passage le même jour (essai 2 à 18:20) n'envoie rien de plus
    assert cli.main(["--point", "bourse", "--essai", "2"]) == 0
    assert len(envoyes) == 1


def test_seance_non_publiee_essai_1_silence_essai_2_annonce(env):
    etat, envoyes, _, heure = env
    heure(LUNDI_1720)
    assert cli.main(["--point", "bourse", "--essai", "1"]) == 0
    assert envoyes == []  # 17:20 : on attend le nouvel essai
    assert cli.main(["--point", "bourse", "--essai", "2"]) == 0
    assert "Séance du 16/11/2026 non encore publiée" in envoyes[0][1]
    assert "Dernière séance disponible : 13/11/2026" in envoyes[0][1]


def test_source_muette_message_explicite_a_l_essai_2(env):
    etat, envoyes, mp, heure = env
    mp.setattr(cli.mizeniti, "charger", lambda *a, **k: (None, taux()))
    assert cli.main(["--point", "bourse", "--essai", "2"]) == 0
    assert "indisponibles" in envoyes[0][1]


def test_weekend_et_jour_ferie_aucun_message(env):
    etat, envoyes, _, heure = env
    heure(datetime(2026, 11, 14, 16, 20, tzinfo=UTC))  # samedi
    assert cli.main(["--point", "bourse", "--essai", "2"]) == 0
    heure(datetime(2026, 12, 17, 16, 20, tzinfo=UTC))  # jeudi, fête de la Révolution
    assert cli.main(["--point", "bourse", "--essai", "2"]) == 0
    assert envoyes == []


def test_cloture_internationale(env):
    _, envoyes, _, heure = env
    heure(datetime(2026, 11, 13, 21, 45, tzinfo=UTC))
    assert cli.main(["--point", "international"]) == 0
    assert envoyes[0][0] == "marches" and "Clôture internationale" in envoyes[0][1]
    assert "MASI : —" in envoyes[0][1] and "Sources : Yahoo Finance, BCT" in envoyes[0][1]


def test_point_et_essai_lus_dans_l_horaire_du_workflow(env):
    _, envoyes, mp, heure = env
    heure(LUNDI_1720)
    mp.setenv("MARCHES_SCHEDULE", "20 16 * * 1-5")  # 17:20 -> bourse, essai 1
    assert cli.main([]) == 0 and envoyes == []
    mp.setenv("MARCHES_SCHEDULE", "20 17 * * 1-5")  # 18:20 -> bourse, essai 2
    assert cli.main([]) == 0 and "non encore publiée" in envoyes[0][1]


def test_panne_telegram_code_non_nul_et_pas_de_marque_d_envoi(env):
    etat, envoyes, mp, _ = env

    def en_panne(*a, **k):
        raise RuntimeError("Telegram indisponible")

    mp.setattr(cli, "envoyer", en_panne)
    assert cli.main(["--point", "bourse", "--essai", "1"]) == 1
    assert etat.lire_json("state/marches.json", {}) == {}  # on pourra réessayer


def test_sans_argument_ni_horaire_usage(env):
    assert cli.main([]) == 2


def test_essai_manuel_avec_jour_impose_ignore_week_end_doublon_et_memorisation(env):
    etat, envoyes, _, heure = env
    heure(datetime(2026, 11, 15, 0, 30, tzinfo=UTC))  # dimanche
    assert cli.main(["--point", "bourse", "--essai", "2", "--jour", "2026-11-13"]) == 0
    assert "séance du 13/11/2026" in envoyes[0][1]
    assert cli.main(["--point", "bourse", "--essai", "2", "--jour", "2026-11-13"]) == 0
    assert len(envoyes) == 2 and etat.lire_json("state/marches.json", {}) == {}
