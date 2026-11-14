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
