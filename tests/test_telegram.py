import html
import re

import pytest

from tests.conftest import FausseReponse, FauxClient
from veille.journal import Journal
from veille.telegram import (
    ENTETES,
    ErreurTelegram,
    decouper,
    envoyer,
    html_vers_texte,
)

BALISE = re.compile(r"<(/?)([a-zA-Z-]+)[^>]*>")


def equilibre(morceau: str) -> bool:
    """Chaque balise ouverte est refermée, dans le bon ordre, et aucun « < » orphelin."""
    pile = []
    for m in BALISE.finditer(morceau):
        if m.group(1):
            if not pile or pile.pop() != m.group(2):
                return False
        else:
            pile.append(m.group(2))
    sans_balises = BALISE.sub("", morceau)
    return not pile and "<" not in sans_balises and ">" not in sans_balises


def texte_visible(morceaux) -> str:
    brut = "".join(BALISE.sub("", m) for m in morceaux)
    return re.sub(r"\s+", "", html.unescape(brut))


# --- A6 : découpage ---------------------------------------------------------------------


def test_message_court_non_decoupe():
    assert decouper("<b>Bonjour</b>", 4096) == ["<b>Bonjour</b>"]


def test_decoupe_sur_frontiere_de_paragraphe():
    paragraphes = [f"<b>Sujet {i}</b>\n" + ("mot " * 60).strip() for i in range(40)]
    message = "\n\n".join(paragraphes)
    assert len(message) > 4096
    morceaux = decouper(message, 4096)
    assert len(morceaux) >= 2
    for m in morceaux:
        assert len(m) <= 4096
        assert equilibre(m)
    # un paragraphe n'est jamais coupé en deux quand il tient dans un message
    for p in paragraphes:
        assert sum(p in m for m in morceaux) == 1


def test_balise_qui_traverse_la_coupure_est_fermee_puis_rouverte():
    lien = '<a href="https://exemple.tn/article?id=1&amp;x=2">'
    message = "<b>" + lien + ("texte long " * 600) + "</a></b>"
    assert len(message) > 4096
    morceaux = decouper(message, 4096)
    assert len(morceaux) >= 2
    for m in morceaux:
        assert len(m) <= 4096
        assert equilibre(m)
    assert morceaux[1].startswith("<b>" + lien)
    assert texte_visible(morceaux) == texte_visible([message])


def test_mot_geant_decoupe_sans_perdre_de_caracteres_ni_couper_une_entite():
    message = "début &amp; " + ("x" * 9000) + " &lt;fin&gt;"
    morceaux = decouper(message, 4096)
    assert all(len(m) <= 4096 for m in morceaux)
    assert texte_visible(morceaux) == texte_visible([message])
    assert all(not re.search(r"&[a-z]*$", m) for m in morceaux)  # pas d'entité coupée


def test_limite_exacte():
    message = "a" * 4096
    assert decouper(message, 4096) == [message]
    assert len(decouper(message + "b", 4096)) == 2


def test_contenu_conserve_pour_un_long_message_realiste():
    blocs = []
    for i in range(80):
        blocs.append(
            f'<b>Chapitre {i}</b>\n• <a href="https://exemple.tn/a/{i}?utm=1&amp;b=2">'
            f"Titre de l'article numéro {i} sur l'économie</a> (FR)\n"
            + "Phrase rédigée par l'IA. "
            * 8
        )
    message = "\n\n".join(blocs)
    morceaux = decouper(message, 4096)
    assert all(len(m) <= 4096 and equilibre(m) for m in morceaux)
    assert texte_visible(morceaux) == texte_visible([message])


# --- texte brut -------------------------------------------------------------------------


def test_html_vers_texte_garde_les_liens():
    h = 'Voir <a href="https://exemple.tn/x?a=1&amp;b=2">l\'article</a> &amp; <b>plus</b>'
    assert html_vers_texte(h) == "Voir l'article (https://exemple.tn/x?a=1&b=2) & plus"


# --- envoi ------------------------------------------------------------------------------


def ok(id_=1):
    return FausseReponse(200, json_={"ok": True, "result": {"message_id": id_}})


def envoyer_avec(scenario, corps, type_="alerte", **kw):
    c = FauxClient(scenario)
    j = Journal(sortie=lambda _: None)
    j.enregistrer_secret("111:SECRET-TOKEN")
    res = envoyer(type_, corps, token="111:SECRET-TOKEN", chat_id="42", client=c, journal=j, **kw)
    return res, c, j


def test_entetes_par_type():
    assert ENTETES["alerte"].startswith("🔔")
    assert ENTETES["matin"].startswith("🌅")
    assert ENTETES["soir"].startswith("🌆")
    assert ENTETES["marches"].startswith("📈")
    assert ENTETES["awb"].startswith("🏦")
    assert ENTETES["sante"].startswith("⚠️")


def test_envoi_simple_avec_entete_et_parametres():
    res, c, _ = envoyer_avec([ok()], "Corps du message")
    assert res.parties == 1 and not res.repli_texte
    appel = c.appels[0]
    assert appel["url"] == "https://api.telegram.org/bot111:SECRET-TOKEN/sendMessage"
    charge = appel["json"]
    assert charge["chat_id"] == "42"
    assert charge["parse_mode"] == "HTML"
    assert charge["text"].startswith("🔔 <b>Alerte</b>\n\nCorps du message")
    assert charge["link_preview_options"] == {"is_disabled": True}


def test_long_message_envoye_en_plusieurs_parties_numerotees():
    corps = "\n\n".join(f"<b>Sujet {i}</b>\n" + "mot " * 80 for i in range(40))
    res, c, _ = envoyer_avec([ok(1), ok(2), ok(3), ok(4)], corps, type_="matin")
    assert res.parties == len(c.appels) >= 2
    textes = [a["json"]["text"] for a in c.appels]
    assert all(len(t) <= 4096 for t in textes)
    assert all(equilibre(t) for t in textes)
    assert f"(1/{res.parties})" in textes[0]
    assert f"({res.parties}/{res.parties})" in textes[-1]


def test_repli_texte_brut_si_telegram_refuse_le_html():
    refus = FausseReponse(
        400,
        json_={"ok": False, "description": "Bad Request: can't parse entities: Unsupported tag"},
    )
    res, c, j = envoyer_avec([refus, ok()], "<b>Titre</b> <a href='https://x.tn'>lien</a>")
    assert res.repli_texte
    assert "parse_mode" not in c.appels[1]["json"]
    assert "<b>" not in c.appels[1]["json"]["text"]
    assert j.avec_niveau("avertissement")[0]["code"] == "telegram_repli_texte"


def test_autre_erreur_telegram_est_levee_sans_le_token():
    refus = FausseReponse(401, json_={"ok": False, "description": "Unauthorized"})
    c = FauxClient([refus])
    j = Journal(sortie=lambda _: None)
    j.enregistrer_secret("111:SECRET-TOKEN")
    with pytest.raises(ErreurTelegram) as e:
        envoyer("alerte", "x", token="111:SECRET-TOKEN", chat_id="42", client=c, journal=j)
    assert "SECRET-TOKEN" not in str(e.value)
    assert "401" in str(e.value)


def test_echappement_du_texte_libre():
    from veille.telegram import echapper

    assert echapper("A & B <c>") == "A &amp; B &lt;c&gt;"


def test_decoupe_aleatoire_graine_fixe():
    """Messages variés (balises imbriquées, entités, longs mots) : jamais de balise cassée."""
    import random

    hasard = random.Random(20261114)
    mots = ["économie", "BCT", "&amp;", "&lt;", "taux", "x" * 300, "a", "été", "—", "TMM+0,25"]
    for _ in range(60):
        morceaux_de_texte = []
        for _ in range(hasard.randint(30, 400)):
            m = hasard.choice(mots)
            r = hasard.random()
            if r < 0.12:
                m = f"<b>{m}</b>"
            elif r < 0.2:
                m = f'<a href="https://exemple.tn/{hasard.randint(1, 999)}?a=1&amp;b=2">{m}</a>'
            elif r < 0.25:
                m = f"<i><b>{m}</b></i>"
            morceaux_de_texte.append(m)
            morceaux_de_texte.append(hasard.choice([" ", " ", " ", "\n", "\n\n"]))
        message = "".join(morceaux_de_texte)
        limite = hasard.choice([400, 1000, 4000])
        morceaux = decouper(message, limite)
        assert all(len(m) <= limite for m in morceaux)
        assert all(equilibre(m) for m in morceaux)
        assert texte_visible(morceaux) == texte_visible([message])
