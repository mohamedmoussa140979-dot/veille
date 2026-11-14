"""Message Telegram de l'édition et archive HTML (A4 côté sorties)."""

import copy
import json
from datetime import date

from tests.test_edition import produire
from tests.test_telegram import equilibre
from veille.edition import archive, message
from veille.telegram import decouper


def edition():
    return produire()[0]


# --- message Telegram -------------------------------------------------------------------


def test_message_essentiel_puis_chapitres_puis_lien_vers_l_edition_complete():
    ed = edition()
    m = message.construire_message(ed, "https://x.github.io/veille/editions/2026-11-17-matin.html")
    assert m.index("L'essentiel") < m.index("Économie tunisienne") < m.index("Technologie")
    assert m.rstrip().endswith("Édition complète</a>")
    assert 'href="https://x.github.io/veille/editions/2026-11-17-matin.html"' in m
    assert "(Réglementation)" in m and "🏠 Les crédits à taux variable augmentent." in m


def test_message_liens_vers_tous_les_articles_lien_fr_et_cadenas():
    m = message.construire_message(edition())
    assert 'href="https://exemple.tn/a1"' in m and 'href="https://exemple.tn/a2"' in m
    assert ">FR</a>" in m  # article anglais non payant
    assert "Bloomberg</a> 🔒" in m  # source payante : cadenas, pas de lien FR


def test_message_echappe_le_html_des_titres():
    ed = edition()
    ed["chapitres"][0]["sujets"][0]["titre"] = "<script>alert(1)</script> & <b>gras</b>"
    m = message.construire_message(ed)
    assert "<script>" not in m and "&lt;script&gt;" in m
    assert equilibre(m)


def test_message_decoupe_sans_balise_cassee_quand_il_depasse_4096():
    ed = edition()
    modele = ed["chapitres"][0]["sujets"][0]
    ed["chapitres"][0]["sujets"] = [
        copy.deepcopy(modele) | {"titre": f"Sujet {i} " + "mot " * 25} for i in range(5)
    ]
    ed["chapitres"] = ed["chapitres"] * 5  # message très long
    m = message.construire_message(ed)
    assert len(m) > 4096
    morceaux = decouper(m, 4000)
    assert all(len(p) <= 4000 and equilibre(p) for p in morceaux)


# --- archive ----------------------------------------------------------------------------


def editions_de_test():
    a = edition()
    b = copy.deepcopy(a) | {"id": "2026-11-16-soir", "date": "2026-11-16", "edition": "soir"}
    ancienne = copy.deepcopy(a) | {"id": "2026-09-01-matin", "date": "2026-09-01"}
    return [a, b, ancienne]


def test_site_pages_par_edition_index_par_mois_et_index_general(tmp_path):
    fichiers = archive.construire_site(editions_de_test(), tmp_path, date(2026, 11, 17))
    noms = {f.relative_to(tmp_path).as_posix() for f in fichiers}
    assert {
        "index.html", "recherche.json", "2026-11/index.html", "2026-09/index.html",
        "editions/2026-11-17-matin.html", "editions/2026-11-16-soir.html", "editions/2026-09-01-matin.html",
    } <= noms  # fmt: skip
    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "Novembre 2026" in index and "Septembre 2026" in index
    assert index.index("2026-11-17-matin") < index.index("2026-11-16-soir")  # plus récent d'abord
    mois = (tmp_path / "2026-11" / "index.html").read_text(encoding="utf-8")
    assert "../editions/2026-11-17-matin.html" in mois


def test_page_d_edition_contenu_liens_et_pastilles(tmp_path):
    archive.construire_site(editions_de_test(), tmp_path, date(2026, 11, 17))
    p = (tmp_path / "editions" / "2026-11-17-matin.html").read_text(encoding="utf-8")
    assert "17 novembre 2026" in p and "L'essentiel" in p and "Économie tunisienne" in p
    assert 'href="../index.html"' in p
    assert 'rel="noopener noreferrer"' in p and ">EN</span>" in p and ">FR</a>" in p
    assert "news.google.com" not in p and "<img" not in p  # aucune image
    assert '<meta name="viewport"' in p


def test_archive_echappe_tout_le_texte(tmp_path):
    ed = edition()
    ed["chapitres"][0]["sujets"][0]["titre"] = '"><script>alert(1)</script>'
    ed["articles"]["a1"]["source"] = "<img src=x onerror=alert(1)>"
    archive.construire_site([ed], tmp_path, date(2026, 11, 17))
    p = (tmp_path / "editions" / "2026-11-17-matin.html").read_text(encoding="utf-8")
    assert "<script>alert(1)" not in p and "<img src=x" not in p
    assert "&lt;script&gt;" in p


def test_recherche_limitee_aux_30_derniers_jours(tmp_path):
    archive.construire_site(editions_de_test(), tmp_path, date(2026, 11, 17))
    donnees = json.loads((tmp_path / "recherche.json").read_text(encoding="utf-8"))
    assert {e["date"] for e in donnees} == {"2026-11-17", "2026-11-16"}  # pas septembre
    assert {"id", "date", "edition", "chapitre", "titre", "texte"} == set(donnees[0])


def test_site_sans_edition_reste_valide(tmp_path):
    archive.construire_site([], tmp_path, date(2026, 11, 17))
    assert "Aucune édition" in (tmp_path / "index.html").read_text(encoding="utf-8")
    assert json.loads((tmp_path / "recherche.json").read_text(encoding="utf-8")) == []


# --- V3 : tableaux des chapitres 3 et 4 -------------------------------------------------


def edition_avec_marches():
    from tests.test_marches import bourse, taux, yahoo_complet
    from veille.marches import tableaux

    marches = {
        "chiffres": tableaux.chiffres(bourse(), yahoo_complet(), taux()),
        "tableaux": {
            "bourse-entreprises": tableaux.tableau_bourse(bourse()),
            "international": tableaux.tableau_international(yahoo_complet(), taux()),
        },
    }
    from tests.test_edition import ARTICLES, CLASSEMENT_OK, MAINTENANT, FauxIa, redaction
    from veille.edition.fenetre import fichier_et_id
    from veille.edition.generation import produire_edition
    from veille.journal import Journal

    ident, type_ = fichier_et_id("matin", MAINTENANT)
    return produire_edition(
        ia=FauxIa(CLASSEMENT_OK, redaction()), articles=ARTICLES, type_enregistre=type_,
        ident=ident, maintenant=MAINTENANT, journal=Journal(sortie=lambda _: None), marches=marches,
    )  # fmt: skip


def test_edition_avec_tableaux_et_quatre_chiffres_valide_le_contrat():
    from veille.edition.modele import valider_edition

    ed = edition_avec_marches()
    valider_edition(ed)
    assert [c["valeur"] for c in ed["chiffres"]] == [
        18989.99,
        3.3639,
        ed["chiffres"][2]["valeur"],
        7.0,
    ]
    tableaux_ = {c["cle"]: c["tableau"] for c in ed["chapitres"]}
    assert tableaux_["bourse-entreprises"]["seance"] == "2026-11-13"
    assert tableaux_["international"]["lignes"][0]["cle"] == "brent"
    assert tableaux_["eco-tunisie"] is None


def test_message_telegram_contient_les_tableaux():
    m = message.construire_message(edition_avec_marches())
    assert "Bourse de Tunis · séance du 13/11/2026" in m and "TUNINDEX" in m and "▲ Hausses" in m
    assert "Matières premières" in m and "MASI —" in m and "EUR/TND (BCT)" in m
    assert equilibre(m)


def test_archive_affiche_les_tableaux_avec_liens_et_tirets(tmp_path):
    archive.construire_site([edition_avec_marches()], tmp_path, date(2026, 11, 17))
    p = (tmp_path / "editions" / "2026-11-17-matin.html").read_text(encoding="utf-8")
    assert '<table class="tab">' in p and "Depuis le 1er janvier" in p and "Instrument" in p
    assert "+0,79 %" in p and "<td>—</td>" in p  # MASI sans source : tiret
    assert 'rel="noopener noreferrer"' in p


def test_chapitre_sans_sujet_garde_son_tableau_mais_pas_les_autres():
    ed = edition_avec_marches()
    assert "international" in [c["cle"] for c in ed["chapitres"]]
    from tests.test_edition import ARTICLES, MAINTENANT, FauxIa
    from tests.test_marches import taux, yahoo_complet
    from veille.edition.generation import produire_edition
    from veille.journal import Journal
    from veille.marches import tableaux

    seul = {"tableaux": {"international": tableaux.tableau_international(yahoo_complet(), taux())}}
    cl = {"articles": [{"id": "a1", "chapitre": "eco-tunisie", "sujet": "x", "importance": 2}]}
    red = {
        "essentiel": [{"texte": "T", "sujets": ["s1"]}],
        "sujets": [{"cle": "s1", "titre": "T", "texte": "X"}],
    }
    e = produire_edition(ia=FauxIa(cl, red), articles=ARTICLES[:1], type_enregistre="matin", ident="2026-11-17-matin",
                         maintenant=MAINTENANT, journal=Journal(sortie=lambda _: None), marches=seul)  # fmt: skip
    assert [(c["cle"], len(c["sujets"])) for c in e["chapitres"]] == [
        ("eco-tunisie", 1),
        ("international", 0),
    ]
