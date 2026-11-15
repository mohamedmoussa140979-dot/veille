"""V5 : contrôle de santé (§ 10), message ⚠️ et message du dimanche — critère A8."""

import json
from datetime import UTC, date, datetime, timedelta

import pytest

from veille.config import charger_sources
from veille.etat import EtatGit, EtatLocal
from veille.sante import __main__ as cli
from veille.sante import controle
from veille.sante.message import message_anomalies, message_semaine_complete

MARDI_21H = datetime(2026, 11, 17, 20, 0, tzinfo=UTC)  # 21:00 à Tunis
DIMANCHE_21H = datetime(2026, 11, 15, 20, 0, tzinfo=UTC)


def src(id_="business-news", type_="rss", actif=True):
    return {"id": id_, "nom": id_.upper(), "type": type_, "actif": actif}


def stats_dernier(iso):
    return {"dernier_nouvel_article": iso, "premier_passage": "2026-01-01T00:00:00+01:00"}


def codes(anomalies):
    return [a.code for a in anomalies]


# --- A8 : sources muettes selon leur type -----------------------------------------------


def test_a8_source_de_presse_muette_apres_trois_jours_ouvres():
    s = [src()]
    # dernier article vendredi 13/11 ; mardi 17/11 = lundi + mardi ouvrés après lui : 2 jours -> pas d'alerte
    assert (
        controle.controle_sources(
            s, {"business-news": stats_dernier("2026-11-13T10:00:00+01:00")}, MARDI_21H
        )
        == []
    )
    # dernier article jeudi 12/11 : vendredi, lundi, mardi = 3 jours ouvrés -> signalée
    a = controle.controle_sources(
        s, {"business-news": stats_dernier("2026-11-12T10:00:00+01:00")}, MARDI_21H
    )
    assert codes(a) == ["source_muette:business-news"]
    assert (
        "3 jours ouvrés" in a[0].texte and "12/11" in a[0].texte and "actif: false" in a[0].action
    )


def test_a8_delais_par_type_ins_dix_jours_bct_cmf_bvmt_sept_jours():
    maintenant = MARDI_21H
    il_y_a = lambda j: (maintenant - timedelta(days=j)).isoformat()  # noqa: E731
    for type_, limite in (("ins", 10), ("bct", 7), ("cmf", 7), ("bvmt", 7)):
        s = [src("x", type_)]
        assert (
            controle.controle_sources(s, {"x": stats_dernier(il_y_a(limite - 1))}, maintenant) == []
        )
        assert codes(
            controle.controle_sources(s, {"x": stats_dernier(il_y_a(limite))}, maintenant)
        ) == ["source_muette:x"]


def test_source_inactive_jamais_observee_ou_recente_pas_signalee():
    ancien = {"x": stats_dernier("2026-01-01T00:00:00+01:00")}
    assert controle.controle_sources([src("x", actif=False)], ancien, MARDI_21H) == []
    assert controle.controle_sources([src("x")], {}, MARDI_21H) == []


def test_source_illisible_depuis_longtemps():
    st = {
        "x": {
            "erreurs_consecutives": 6,
            "derniere_erreur": "HTTP 403",
            **stats_dernier(MARDI_21H.isoformat()),
        }
    }
    a = controle.controle_sources([src("x")], st, MARDI_21H)
    assert codes(a) == ["source_illisible:x"] and "HTTP 403" in a[0].texte
    st["x"]["erreurs_consecutives"] = 5
    assert controle.controle_sources([src("x")], st, MARDI_21H) == []


def test_jours_ouvres():
    assert (
        controle.jours_ouvres_depuis(date(2026, 11, 13), date(2026, 11, 16)) == 1
    )  # vendredi -> lundi
    assert controle.jours_ouvres_depuis(date(2026, 11, 13), date(2026, 11, 15)) == 0  # week-end
    assert controle.jours_ouvres_depuis(date(2026, 11, 9), date(2026, 11, 16)) == 5


# --- tâches planifiées ------------------------------------------------------------------


def run(nom, il_y_a_h, conclusion="success", id_=1):
    t = MARDI_21H - timedelta(hours=il_y_a_h)
    return {"name": nom, "conclusion": conclusion, "created_at": t.isoformat(), "id": id_,
            "html_url": f"https://github.com/x/y/actions/runs/{id_}"}  # fmt: skip


def runs_sains():
    return [run("collecte", 2), run("edition", 3), run("marches", 20), run("awb", 4)]


def test_taches_saines_aucune_anomalie():
    assert controle.controle_taches(runs_sains(), MARDI_21H) == []


def test_tache_qui_ne_tourne_plus_et_tache_en_echec():
    runs = [r for r in runs_sains() if r["name"] != "awb"] + [
        run("awb", 30)
    ]  # dernier succès il y a 30 h
    runs.append(run("collecte", 1, "failure", id_=99))
    a = controle.controle_taches(runs, MARDI_21H)
    assert "tache_muette:awb" in codes(a) and "tache_en_echec:collecte:99" in codes(a)
    echec = next(x for x in a if x.code.startswith("tache_en_echec"))
    assert "actions/runs/99" in echec.action


def test_un_echec_ancien_de_plus_de_24_heures_n_est_pas_signale():
    assert (
        controle.controle_taches(runs_sains() + [run("edition", 40, "failure", 7)], MARDI_21H) == []
    )


def test_un_essai_manuel_en_echec_n_est_pas_une_panne_de_tache_planifiee():
    manuel = run("edition", 1, "failure", id_=8) | {"event": "workflow_dispatch"}
    planifie = run("edition", 1, "failure", id_=9) | {"event": "schedule"}
    assert controle.controle_taches(runs_sains() + [manuel], MARDI_21H) == []
    assert codes(controle.controle_taches(runs_sains() + [planifie], MARDI_21H)) == [
        "tache_en_echec:edition:9"
    ]


def test_workflow_jamais_execute_signale():
    assert "tache_muette:marches" in codes(
        controle.controle_taches([r for r in runs_sains() if r["name"] != "marches"], MARDI_21H)
    )


# --- éditions ---------------------------------------------------------------------------


def test_editions_manquantes_semaine_et_weekend():
    assert (
        controle.controle_editions(
            {"editions/2026-11-17-matin.json", "editions/2026-11-17-soir.json"}, MARDI_21H
        )
        == []
    )
    a = controle.controle_editions({"editions/2026-11-17-matin.json"}, MARDI_21H)
    assert codes(a) == ["edition_manquante:2026-11-17-soir"] and "17/11" in a[0].texte
    assert len(controle.controle_editions(set(), MARDI_21H)) == 2
    assert (
        controle.controle_editions({"editions/2026-11-15-matin.json"}, DIMANCHE_21H) == []
    )  # une seule le week-end
    assert codes(controle.controle_editions(set(), DIMANCHE_21H)) == [
        "edition_manquante:2026-11-15-matin"
    ]


# --- IA ---------------------------------------------------------------------------------


def ev(code):
    return {"code": code, "niveau": "avertissement", "t": MARDI_21H.isoformat()}


def test_gemini_en_echec_et_claude_utilise_et_plafond():
    assert controle.controle_ia([], {}, 5.0, MARDI_21H) == []
    assert codes(controle.controle_ia([ev("claude_secours_utilise")], {}, 5.0, MARDI_21H)) == [
        "claude_utilise"
    ]
    quatre = {"2026-11": {"usd": 4.0}}
    a = controle.controle_ia([], quatre, 5.0, MARDI_21H)
    assert codes(a) == ["claude_plafond_80"] and "80 %" in a[0].texte
    assert controle.controle_ia([], {"2026-11": {"usd": 3.9}}, 5.0, MARDI_21H) == []
    assert codes(controle.controle_ia([], {"2026-11": {"usd": 5.0}}, 5.0, MARDI_21H)) == [
        "claude_plafond_atteint"
    ]
    assert codes(controle.controle_ia([ev("claude_plafond_atteint")], {}, 5.0, MARDI_21H)) == [
        "claude_plafond_atteint"
    ]


# --- données de marché et traduction ----------------------------------------------------


def test_yahoo_traduction_et_bourse_perimee():
    attendue = date(2026, 11, 17)
    assert controle.controle_donnees([], "2026-11-17", attendue) == []
    a = controle.controle_donnees(
        [ev("yahoo_echec"), ev("yahoo_sans_donnee"), ev("awb_traduction_sans_donnee")],
        "2026-11-17",
        attendue,
    )
    assert codes(a) == ["yahoo_sans_donnee", "traduction_awb"] and "2 cotation" in a[0].texte
    p = controle.controle_donnees([], "2026-11-13", attendue)
    assert codes(p) == ["bourse_perimee"] and "13/11" in p[0].texte and "17/11" in p[0].texte
    assert codes(controle.controle_donnees([], None, attendue)) == ["bourse_muette"]


def test_dernier_jour_ouvre_week_end_et_jour_ferie():
    assert controle.dernier_jour_ouvre(DIMANCHE_21H, set()) == date(2026, 11, 13)  # vendredi
    assert controle.dernier_jour_ouvre(MARDI_21H, set()) == date(2026, 11, 17)
    assert controle.dernier_jour_ouvre(MARDI_21H, {"2026-11-17"}) == date(2026, 11, 16)


# --- messages ---------------------------------------------------------------------------


def test_message_anomalies_une_ligne_par_anomalie_avec_action_et_html_echappe():
    a = [
        controle.Anomalie("x", "Source <A> & B muette", "vérifier"),
        controle.Anomalie("y", "Autre", "relancer"),
    ]
    m = message_anomalies(a, "Cette semaine : 9 éditions, 4 alertes.")
    assert m.startswith("<b>2 anomalies à regarder</b>") and "Source &lt;A&gt; &amp; B muette" in m
    assert "➜ vérifier" in m and "➜ relancer" in m and m.endswith("4 alertes.")
    assert message_anomalies(a[:1]).startswith("<b>1 anomalie à regarder</b>")
    assert (
        message_semaine_complete(9, 1) == "Aucune anomalie. Cette semaine : 9 éditions, 1 alerte."
    )


# --- passage complet --------------------------------------------------------------------


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    etat = EtatLocal(tmp_path / "etat")
    monkeypatch.setattr(EtatGit, "depuis_environnement", classmethod(lambda cls, *a, **k: etat))
    envoyes = []
    monkeypatch.setattr(cli, "envoyer", lambda type_, corps, **kw: envoyes.append((type_, corps)))
    monkeypatch.setattr("veille.temps.maintenant", lambda: MARDI_21H)
    monkeypatch.setattr(cli, "runs_github", lambda *a, **k: runs_sains())
    monkeypatch.setattr(cli, "date_bourse", lambda *a, **k: "2026-11-17")
    monkeypatch.setenv("TG_TOKEN_VEILLE", "jeton")
    monkeypatch.setenv("TG_CHAT_ID", "42")
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/veille")
    frais = MARDI_21H.isoformat()
    etat.ecrire = None
    etat.modifier_json(
        "state/sources.json",
        lambda d: {s["id"]: stats_dernier(frais) for s in charger_sources()},
        defaut={},
    )
    for f in ("2026-11-17-matin", "2026-11-17-soir"):
        etat.ajouter_lignes(f"editions/{f}.json", ["{}"])
    etat.modifier_json(
        "state/alertes_stats.json",
        lambda d: {"2026-11-16": 2, "2026-11-12": 1, "2026-11-01": 9},
        defaut={},
    )
    return etat, envoyes, monkeypatch


def test_tout_va_bien_en_semaine_aucun_message(env):
    etat, envoyes, _ = env
    assert cli.main([]) == 0 and envoyes == []
    assert "sante_controle" in (etat.lire("sante/2026-11.jsonl") or "")


def test_source_muette_message_groupe_avec_action(env):
    etat, envoyes, _ = env
    etat.modifier_json(
        "state/sources.json",
        lambda d: {**d, "business-news": stats_dernier("2026-11-10T10:00:00+01:00")},
        defaut={},
    )
    assert cli.main([]) == 0
    assert envoyes[0][0] == "sante" and "BUSINESS-NEWS" not in envoyes[0][1]
    assert (
        "Business News" in envoyes[0][1]
        and "aucun nouvel article" in envoyes[0][1]
        and "➜" in envoyes[0][1]
    )


def test_dimanche_sans_anomalie_message_semaine_complete(env):
    etat, envoyes, mp = env
    mp.setattr("veille.temps.maintenant", lambda: DIMANCHE_21H)
    mp.setattr(cli, "date_bourse", lambda *a, **k: "2026-11-13")
    mp.setattr(
        cli,
        "runs_github",
        lambda *a, **k: [run_dimanche(n) for n in ("collecte", "edition", "marches", "awb")],
    )
    etat.modifier_json(
        "state/sources.json",
        lambda d: {s["id"]: stats_dernier(DIMANCHE_21H.isoformat()) for s in charger_sources()},
        defaut={},
    )
    etat.ajouter_lignes("editions/2026-11-15-matin.json", ["{}"])
    assert cli.main([]) == 0
    assert envoyes[0][0] == "sante_ok" and "Aucune anomalie" in envoyes[0][1]
    assert (
        "3 éditions" in envoyes[0][1] and "3 alertes" in envoyes[0][1]
    )  # 17, 17 et 15/11 ; alertes du 16 et du 12


def run_dimanche(nom):
    t = DIMANCHE_21H - timedelta(hours=3)
    return {
        "name": nom,
        "conclusion": "success",
        "created_at": t.isoformat(),
        "id": 5,
        "html_url": "x",
    }


def test_dimanche_avec_anomalie_un_seul_message_avec_la_semaine(env):
    etat, envoyes, mp = env
    mp.setattr("veille.temps.maintenant", lambda: DIMANCHE_21H)
    mp.setattr(cli, "date_bourse", lambda *a, **k: "2026-11-13")
    mp.setattr(
        cli,
        "runs_github",
        lambda *a, **k: [run_dimanche(n) for n in ("collecte", "edition", "marches", "awb")],
    )
    assert (
        cli.main([]) == 0
    )  # sources du fixture : vieilles de 4 jours pour ce dimanche, éditions du dimanche absentes
    assert len(envoyes) == 1 and envoyes[0][0] == "sante" and "Cette semaine" in envoyes[0][1]


def test_telegram_en_panne_code_non_nul(env):
    etat, envoyes, mp = env
    etat.modifier_json(
        "state/sources.json",
        lambda d: {**d, "business-news": stats_dernier("2026-11-01T10:00:00+01:00")},
        defaut={},
    )

    def panne(*a, **k):
        raise RuntimeError("indisponible")

    mp.setattr(cli, "envoyer", panne)
    assert cli.main([]) == 1
    assert "sante_telegram_echec" in (etat.lire("sante/2026-11.jsonl") or "")


def test_evenements_des_24_dernieres_heures_seulement(env):
    etat, _, _ = env
    recent = {
        "t": (MARDI_21H - timedelta(hours=3)).isoformat(),
        "code": "yahoo_echec",
        "niveau": "avertissement",
    }
    ancien = {
        "t": (MARDI_21H - timedelta(hours=30)).isoformat(),
        "code": "claude_secours_utilise",
        "niveau": "avertissement",
    }
    etat.ajouter_lignes(
        "sante/2026-11.jsonl", [json.dumps(recent), json.dumps(ancien), "pas du json"]
    )
    assert [e["code"] for e in cli.charger_evenements(etat, MARDI_21H)] == ["yahoo_echec"]
