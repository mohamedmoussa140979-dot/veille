from datetime import UTC, datetime

from veille import temps
from veille.journal import Journal


def test_heure_de_tunis_est_utc_plus_un_toute_l_annee():
    ete = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    hiver = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    assert temps.en_tunis(ete).hour == 13
    assert temps.en_tunis(hiver).hour == 13


def test_mois_courant_suit_l_heure_de_tunis():
    # 23:30 UTC le 30/11 = 00:30 le 1er/12 à Tunis
    assert temps.mois(datetime(2026, 11, 30, 23, 30, tzinfo=UTC)) == "2026-12"
    assert temps.mois(datetime(2026, 11, 30, 22, 30, tzinfo=UTC)) == "2026-11"


def test_le_journal_masque_les_secrets_enregistres():
    sortie = []
    j = Journal(sortie=sortie.append)
    j.enregistrer_secret("tok_SECRET_123")
    j.avertir("essai", "échec sur https://api.exemple/tok_SECRET_123/x", cle="tok_SECRET_123")
    assert "tok_SECRET_123" not in sortie[0]
    assert "tok_SECRET_123" not in str(j.evenements)
    assert "***" in sortie[0]


def test_les_secrets_trop_courts_ne_sont_pas_masques():
    # masquer « 1 » ou « ab » détruirait tout le texte
    j = Journal(sortie=lambda _: None)
    j.enregistrer_secret("ab")
    assert j.masquer("abc") == "abc"


def test_depuis_env_enregistre_les_valeurs_des_variables(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "valeur-gemini-secrete")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    j = Journal.depuis_env(sortie=lambda _: None)
    assert "valeur-gemini-secrete" not in j.masquer("clé valeur-gemini-secrete")


def test_evenements_et_serialisation_jsonl():
    j = Journal(sortie=lambda _: None, horloge=lambda: datetime(2026, 11, 14, 20, 0, tzinfo=UTC))
    j.info("demarrage", "ok", lot="V0")
    j.erreur("panne", "boum")
    lignes = j.vers_jsonl().strip().split("\n")
    assert len(lignes) == 2
    assert '"code": "demarrage"' in lignes[0]
    assert '"t": "2026-11-14T21:00:00+01:00"' in lignes[0]
    assert j.avec_niveau("erreur")[0]["code"] == "panne"
