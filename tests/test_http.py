import pytest
import requests

from tests.conftest import FausseReponse
from veille.http import Client, ErreurReseau, encoder_url
from veille.journal import Journal


class FausseSession:
    """Session requests scénarisée ; enregistre les appels."""

    def __init__(self, scenario):
        self.scenario = list(scenario)
        self.appels = []

    def request(self, methode, url, **kw):
        self.appels.append((methode, url, kw))
        suivant = self.scenario.pop(0)
        if isinstance(suivant, Exception):
            raise suivant
        return suivant


def client(scenario, **kw):
    pauses = []
    session = FausseSession(scenario)
    c = Client(session=session, sleep=pauses.append, attente=1.0, **kw)
    return c, session, pauses


# --- encodage des URL -------------------------------------------------------------------


def test_encoder_url_accents_dans_le_chemin():
    # cas réel : France24 plantait sur l'accent de l'URL
    assert (
        encoder_url("https://www.france24.com/fr/économie/rss")
        == "https://www.france24.com/fr/%C3%A9conomie/rss"
    )


def test_encoder_url_ne_double_pas_l_encodage():
    url = "https://exemple.tn/a%C3%A9/b?q=%C3%A9"
    assert encoder_url(url) == url


def test_encoder_url_espaces_et_requete():
    assert encoder_url("https://exemple.tn/a b?x=é y&z=1") == (
        "https://exemple.tn/a%20b?x=%C3%A9%20y&z=1"
    )


def test_encoder_url_retire_le_fragment_et_garde_les_caracteres_utiles():
    assert encoder_url("https://exemple.tn/p?id=1&b=2#haut") == "https://exemple.tn/p?id=1&b=2"


def test_encoder_url_hote_idn():
    assert encoder_url("https://café.tn/x") == "https://xn--caf-dma.tn/x"


# --- nouveaux essais --------------------------------------------------------------------


def test_succes_du_premier_coup_sans_pause():
    c, s, pauses = client([FausseReponse(200)])
    assert c.get("https://exemple.tn/").status_code == 200
    assert pauses == []
    assert len(s.appels) == 1


def test_503_puis_succes_avec_attente_croissante():
    c, s, pauses = client([FausseReponse(503), FausseReponse(503), FausseReponse(200)], essais=3)
    assert c.get("https://exemple.tn/").status_code == 200
    assert pauses == [1.0, 2.0]


def test_404_n_est_pas_reessaye():
    c, s, pauses = client([FausseReponse(404)])
    assert c.get("https://exemple.tn/x").status_code == 404
    assert len(s.appels) == 1


def test_essais_epuises_sur_statut_renvoie_la_derniere_reponse():
    c, s, _ = client([FausseReponse(503), FausseReponse(502)], essais=2)
    assert c.get("https://exemple.tn/").status_code == 502


def test_erreur_de_connexion_reessayee_puis_ErreurReseau():
    c, s, pauses = client(
        [requests.ConnectionError("boum"), requests.Timeout("lent")], essais=2
    )
    with pytest.raises(ErreurReseau):
        c.get("https://exemple.tn/")
    assert len(s.appels) == 2
    assert len(pauses) == 1


def test_retry_after_en_secondes_est_respecte_et_plafonne():
    c, _, pauses = client(
        [FausseReponse(429, entetes={"Retry-After": "7"}), FausseReponse(200)], essais=2
    )
    c.get("https://exemple.tn/")
    assert pauses == [7.0]
    c2, _, pauses2 = client(
        [FausseReponse(429, entetes={"Retry-After": "9999"}), FausseReponse(200)],
        essais=2,
        attente_max=30.0,
    )
    c2.get("https://exemple.tn/")
    assert pauses2 == [30.0]


def test_retry_after_dans_le_corps_json_style_telegram():
    corps = {"ok": False, "parameters": {"retry_after": 3}}
    c, _, pauses = client([FausseReponse(429, json_=corps), FausseReponse(200)], essais=2)
    c.post("https://api.telegram.org/botXXXX/sendMessage", json={})
    assert pauses == [3.0]


def test_essais_surcharges_par_appel():
    c, s, _ = client([FausseReponse(503)], essais=3)
    assert c.get("https://exemple.tn/", essais=1).status_code == 503
    assert len(s.appels) == 1


# --- hygiène ----------------------------------------------------------------------------


def test_en_tetes_navigateur_par_defaut_et_url_encodee():
    c, s, _ = client([FausseReponse(200)])
    c.get("https://exemple.tn/é")
    methode, url, kw = s.appels[0]
    assert url == "https://exemple.tn/%C3%A9"
    assert "Mozilla/5.0" in kw["headers"]["User-Agent"]
    assert kw["headers"]["Accept-Language"].startswith("fr")
    assert kw["timeout"] == 25.0


def test_delai_minimal_par_hote():
    horloge = iter([100.0, 100.0, 100.2, 100.2, 105.0, 105.0])
    pauses = []
    session = FausseSession([FausseReponse(200)] * 3)
    c = Client(session=session, sleep=pauses.append, horloge=lambda: next(horloge), delai_hote=1.0)
    c.get("https://a.tn/1")  # premier appel : pas d'attente
    c.get("https://a.tn/2")  # 0,2 s plus tard : il manque 0,8 s
    c.get("https://b.tn/1")  # autre hôte : pas d'attente
    assert pauses == [pytest.approx(0.8)]


def test_repli_ssl_explicite_et_journalise():
    j = Journal(sortie=lambda _: None)
    session = FausseSession([requests.exceptions.SSLError("certificat"), FausseReponse(200)])
    c = Client(session=session, sleep=lambda _: None, journal=j)
    r = c.get("https://bct.tn/", ssl_repli=True)
    assert r.status_code == 200
    assert session.appels[1][2]["verify"] is False
    assert j.avec_niveau("avertissement")[0]["code"] == "http_ssl_repli"


def test_ssl_sans_repli_est_une_erreur():
    session = FausseSession([requests.exceptions.SSLError("certificat")])
    c = Client(session=session, sleep=lambda _: None, essais=1)
    with pytest.raises(ErreurReseau):
        c.get("https://bct.tn/")


def test_le_message_d_erreur_ne_contient_pas_le_secret():
    j = Journal(sortie=lambda _: None)
    j.enregistrer_secret("123456:TOKEN-SECRET")
    session = FausseSession([requests.ConnectionError("échec https://api/bot123456:TOKEN-SECRET/x")])
    c = Client(session=session, sleep=lambda _: None, essais=1, journal=j)
    with pytest.raises(ErreurReseau) as e:
        c.post("https://api.telegram.org/bot123456:TOKEN-SECRET/sendMessage")
    assert "TOKEN-SECRET" not in str(e.value)
