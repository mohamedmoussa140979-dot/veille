"""V3 : Bourse (Mizeniti), taux BCT, international (Yahoo), tableaux et points 📈 — sans réseau."""

import json
import re
from pathlib import Path

from tests.conftest import FausseReponse
from tests.test_telegram import equilibre
from veille.http import ErreurReseau
from veille.journal import Journal
from veille.marches import mizeniti, points, tableaux, yahoo
from veille.marches.formats import date_courte, nombre, signe

FIX = Path(__file__).parent / "fixtures"


def charger(nom):
    return json.loads((FIX / nom).read_text(encoding="utf-8"))


def bourse():
    return mizeniti.lire_bourse(
        charger("mizeniti_indices.json"),
        charger("mizeniti_index.json"),
        charger("mizeniti_volumes.json"),
    )


def taux():
    return mizeniti.lire_taux(
        charger("mizeniti_tmm.json"), charger("mizeniti_tre.json"), charger("mizeniti_change.json")
    )


# --- formats ----------------------------------------------------------------------------


def test_formats_francais():
    assert nombre(18989.99) == "18 989,99" and nombre(None) == "—" and nombre(3.3639, 4) == "3,3639"
    assert (
        signe(0.79) == "+0,79 %"
        and signe(-1.2) == "−1,20 %"
        and signe(0) == "0,00 %"
        and signe(None) == "—"
    )
    assert date_courte("2026-11-13") == "13/11/2026" and date_courte(None) == "—"


# --- Bourse : A11 -----------------------------------------------------------------------


def test_a11_indices_identiques_a_indices_json_de_mizeniti():
    b, brut = bourse(), {i["code"]: i for i in charger("mizeniti_indices.json")["indices"]}
    tunindex = next(i for i in b["indices"] if i["cle"] == "tunindex")
    assert tunindex["valeur"] == brut["TUNINDEX"]["valeur"] / 100 == 18989.99
    assert (
        tunindex["variation_pct"] == brut["TUNINDEX"]["variation_jour"] == 0.79
    )  # publiée, pas recalculée
    assert tunindex["variation_annee_pct"] == brut["TUNINDEX"]["variation_annee"]
    assert not tunindex["variation_calculee"]
    assert b["seance"] == "2026-11-13" and b["source"] == "Bourse de Tunis"
    banques = next(i for i in b["indices"] if i["cle"] == "banques")
    assert banques["valeur"] == brut["8300"]["valeur"] / 100


def test_variation_non_publiee_calculee_depuis_la_valeur_precedente_et_signalee():
    b = bourse()
    banques = next(i for i in b["indices"] if i["cle"] == "banques")
    brut = next(i for i in charger("mizeniti_indices.json")["indices"] if i["code"] == "8300")
    assert brut["variation_jour"] is None and banques["variation_calculee"]
    assert banques["variation_pct"] == round((brut["valeur"] / brut["precedente"] - 1) * 100, 2)


def test_hausses_et_baisses_ignorent_les_valeurs_non_cotees_du_jour():
    b = bourse()
    index = charger("mizeniti_index.json")
    non_cotees = {v["m"].lower() for v in index["valeurs"] if not v.get("v")}
    assert non_cotees  # la fixture en contient
    cites = {v["cle"] for v in b["hausses"] + b["baisses"]}
    assert not cites & non_cotees
    assert len(b["hausses"]) <= 3 and len(b["baisses"]) <= 3
    assert [v["variation_pct"] for v in b["hausses"]] == sorted(
        (v["variation_pct"] for v in b["hausses"]), reverse=True
    )
    assert all(v["variation_pct"] > 0 for v in b["hausses"]) and all(
        v["variation_pct"] < 0 for v in b["baisses"]
    )


def test_capitaux_de_la_seance_et_donnees_absentes():
    cap = bourse()["capitaux"]
    assert cap["capitaux_mtnd"] == 20.74 and cap["transactions"] == 1724
    sans = mizeniti.lire_bourse(charger("mizeniti_indices.json"), None, None)
    assert sans["hausses"] == [] and sans["capitaux"] is None  # jamais de zéro par défaut
    assert mizeniti.lire_bourse(None, None, None) is None
    assert mizeniti.lire_bourse({"indices": []}, None, None) is None


def test_taux_bct_via_mizeniti():
    t = taux()
    assert t["tmm"]["valeur"] == 7.0 and t["tmm"]["periode"] == "2026-10"
    assert t["eur_tnd"]["valeur"] == 3.3639 and t["usd_tnd"]["valeur"] == 3.0335
    assert t["eur_tnd"]["au"] == "2026-11-12" and t["eur_tnd"]["source_url"].startswith(
        "https://www.bct.gov.tn"
    )
    assert mizeniti.lire_taux(None, None, None) == {
        "tmm": None,
        "tre": None,
        "eur_tnd": None,
        "usd_tnd": None,
    }


class ClientParUrl:
    def __init__(self, routes):
        self.routes, self.appels = routes, []

    def get(self, url, **kw):
        self.appels.append(url)
        for fin, rep in self.routes.items():
            if url.endswith(fin):
                if isinstance(rep, Exception):
                    raise rep
                return rep
        return FausseReponse(404)


def routes_mizeniti(**surcharge):
    base = {
        "/marche/bourse/indices.json": FausseReponse(200, json_=charger("mizeniti_indices.json")),
        "/marche/bourse/index.json": FausseReponse(200, json_=charger("mizeniti_index.json")),
        "/marche/bourse/volumes.json": FausseReponse(200, json_=charger("mizeniti_volumes.json")),
        "/marche/taux/tmm.json": FausseReponse(200, json_=charger("mizeniti_tmm.json")),
        "/marche/taux/tre.json": FausseReponse(200, json_=charger("mizeniti_tre.json")),
        "/marche/taux/change.json": FausseReponse(200, json_=charger("mizeniti_change.json")),
    }
    return {**base, **surcharge}


def test_charger_lit_les_six_routes_en_lecture_seule():
    client = ClientParUrl(routes_mizeniti())
    b, t = mizeniti.charger(client, "https://marche.exemple.test/")
    assert b and t["tmm"] and len(client.appels) == 6
    assert all(u.startswith("https://marche.exemple.test/marche/") for u in client.appels)


def test_worker_muet_tiret_explicite_et_avertissement():
    j = Journal(sortie=lambda _: None)
    client = ClientParUrl(routes_mizeniti(**{"/marche/bourse/indices.json": ErreurReseau("délai")}))
    b, t = mizeniti.charger(client, "https://m.test", j)
    assert b is None and t["tmm"]  # la Bourse est muette, les taux répondent
    assert j.avec_niveau("avertissement")[0]["code"] == "mizeniti_muet"


def test_a11_aucun_rediffuseur_dans_le_code_des_marches():
    interdits = re.compile(r"irbe7|ilboursa|tustex|tera[-_ ]?finances|african[-_ ]?markets", re.I)
    for f in (Path(__file__).parent.parent / "veille" / "marches").glob("*.py"):
        assert not interdits.search(f.read_text(encoding="utf-8")), f.name


# --- Yahoo ------------------------------------------------------------------------------


def test_lire_chart_prix_variation_et_date():
    c = yahoo.lire_chart(charger("yahoo_brent.json"))
    assert c["valeur"] > 0 and c["devise"] == "USD" and c["au"]
    assert c["variation_pct"] == round((c["valeur"] / c["precedent"] - 1) * 100, 2)
    assert yahoo.lire_chart({"chart": {"result": None}}) is None and yahoo.lire_chart({}) is None


def test_internationaux_un_instrument_en_panne_n_arrete_pas_les_autres():
    ok = FausseReponse(200, json_=charger("yahoo_brent.json"))
    client = ClientParUrl({"BZ=F": ok, "NG=F": ErreurReseau("panne"), "GC=F": FausseReponse(500), "ZW=F": ok,
                           "^GSPC": ok, "^STOXX50E": ok, "^FCHI": ok, "EURUSD=X": ok})  # fmt: skip
    j = Journal(sortie=lambda _: None)
    res = yahoo.lire_internationaux(client, j)
    assert res["brent"] and res["sp500"] and res["blé" if False else "ble"]
    assert res["gaz"] is None and res["or"] is None  # tiret, jamais 0
    assert res["masi"] is None and not any(
        "MASI" in u for u in client.appels
    )  # pas de symbole : pas d'appel
    assert res["brent"]["source_url"] == "https://finance.yahoo.com/quote/BZ%3DF"
    codes = [e["code"] for e in j.evenements]
    assert "yahoo_echec" in codes and "yahoo_sans_donnee" in codes


# --- tableaux, chiffres -----------------------------------------------------------------


def yahoo_complet():
    ok = yahoo.lire_chart(charger("yahoo_brent.json"))
    return {cle: {**ok, "libelle": lib, "unite": u, "source_url": f"https://finance.yahoo.com/quote/{cle}"} if sym else None
            for cle, lib, sym, u in yahoo.INSTRUMENTS}  # fmt: skip


def test_tableau_bourse_chapitre_3():
    t = tableaux.tableau_bourse(bourse())
    assert [x["cle"] for x in t["lignes"]] == ["tunindex", "banques"]
    assert t["seance"] == "2026-11-13" and t["provisoire"] is False
    assert len(t["hausses"]) == 3 and len(t["baisses"]) == 3
    assert all(
        x["source_url"].startswith("https://") for x in t["lignes"] + t["hausses"] + t["baisses"]
    )
    assert tableaux.tableau_bourse(None) is None


def test_tableau_international_chapitre_4_neuf_instruments_et_deux_cours_bct():
    t = tableaux.tableau_international(yahoo_complet(), taux())
    assert [x["cle"] for x in t["lignes"]] == [
        "brent", "gaz", "or", "ble", "sp500", "eurostoxx50", "cac40", "masi", "eurusd", "eur_tnd", "usd_tnd"
    ]  # fmt: skip
    masi = next(x for x in t["lignes"] if x["cle"] == "masi")
    assert masi["valeur"] is None and masi["source_url"] is None
    eur = next(x for x in t["lignes"] if x["cle"] == "eur_tnd")
    assert eur["valeur"] == 3.3639 and eur["unite"] == "dinars"


def test_quatre_chiffres_de_l_en_tete_donnee_absente_vaut_null():
    c = tableaux.chiffres(bourse(), yahoo_complet(), taux())
    assert [x["cle"] for x in c] == ["tunindex", "eur_tnd_bct", "brent", "tmm"]
    assert c[0]["valeur"] == 18989.99 and c[1]["valeur"] == 3.3639 and c[3]["valeur"] == 7.0
    vide = tableaux.chiffres(None, {}, mizeniti.lire_taux(None, None, None))
    assert all(x["valeur"] is None and x["source_url"] is None for x in vide)  # jamais 0


# --- messages 📈 ------------------------------------------------------------------------


def test_message_bourse_contenu_et_html_valide():
    m = points.message_bourse(bourse(), "2026-11-13")
    assert "séance du 13/11/2026" in m and "TUNINDEX" in m and "+0,79 %" in m
    assert "Indice des Banques" in m and "Plus fortes hausses" in m and "Plus fortes baisses" in m
    assert "Capitaux échangés" in m and "20,74 MTND" in m and "Source : Bourse de Tunis" in m
    assert equilibre(m)


def test_message_bourse_provisoire_non_publiee_et_muette():
    b = bourse()
    b["provisoire"] = True
    assert "(provisoire)" in points.message_bourse(b, "2026-11-13")
    assert points.message_bourse(bourse(), "2026-11-16").startswith(
        "Séance du 16/11/2026 non encore publiée"
    )
    assert "indisponibles" in points.message_bourse(None)


def test_message_international_tiret_pour_les_absents():
    t = tableaux.tableau_international(yahoo_complet(), taux())
    m = points.message_international(t, taux())
    assert (
        "Brent" in m and "MASI : —" in m and "EUR/TND (BCT)" in m and "TMM" in m and "7,00 %" in m
    )
    assert "Source" in m and equilibre(m)
