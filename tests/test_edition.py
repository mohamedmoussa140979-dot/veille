"""A4, A5 : contenu et contrat des éditions, avec une IA simulée (aucun réseau)."""

import copy
import json
from datetime import UTC, datetime

import pytest

from veille.edition.fenetre import (
    calculer_fenetre,
    charger_articles,
    fichier_et_id,
    type_pour,
)
from veille.edition.generation import AucuneActualite, produire_edition
from veille.edition.modele import EditionInvalide, valider_edition
from veille.etat import EtatLocal
from veille.ia import Resultat
from veille.journal import Journal

MAINTENANT = datetime(2026, 11, 17, 6, 30, tzinfo=UTC)  # 07:30 à Tunis, mardi


def art(i, chapitre="eco-tunisie", langue="fr", source="BCT", payant=False, **kw):
    a = {
        "id": i, "source_id": source.lower(), "source": source, "titre": f"Titre {i}",
        "url": f"https://exemple.tn/{i}", "publie_le": f"2026-11-16T{10 + int(i[1:]) % 8:02d}:00:00+01:00",
        "langue": langue, "payant": payant, "resume": f"Résumé de {i}", "chapitre": chapitre,
        "url_traduite": None,
    }  # fmt: skip
    if langue != "fr" and not payant:
        a["url_traduite"] = (
            f"https://x.translate.goog/{i}?_x_tr_sl={langue}&_x_tr_tl=fr&_x_tr_hl=fr"
        )
        a["titre_origine"] = a["titre"]
    return {**a, **kw}


class FauxIa:
    def __init__(self, *reponses):
        self.reponses = list(reponses)
        self.prompts = []

    def generer_json(self, prompt, schema, *, systeme=None, normaliser=None):
        self.prompts.append(prompt)
        donnees = self.reponses.pop(0)
        if normaliser:
            donnees = normaliser(donnees)
        return Resultat("", "gemini", "gemini-test", donnees=donnees, essais=1)


def journal():
    return Journal(sortie=lambda _: None)


def classement(*lignes):
    return {
        "articles": [
            dict(zip(("id", "chapitre", "sujet", "importance", "rubrique"), ligne, strict=False))
            for ligne in lignes
        ]
    }


ARTICLES = [
    art("a1"), art("a2", source="Business News"), art("a3", chapitre="bourse-entreprises", source="CMF"),
    art("a4", chapitre="international", langue="en", source="TechCabal"),
    art("a5", chapitre="international", langue="en", source="Bloomberg", payant=True),
    art("a6", chapitre="technologie", source="Finextra"), art("a7", chapitre="eco-tunisie", source="Sport FM"),
]  # fmt: skip

CLASSEMENT_OK = classement(
    ("a1", "eco-tunisie", "taux", 3, "reglementation"),
    ("a2", "eco-tunisie", "taux", 2, "presse"),  # même fait que a1
    ("a3", "bourse-entreprises", "dividendes", 2),
    ("a4", "international", "fed", 3),
    ("a5", "international", "fed", 3),
    ("a6", "technologie", "fintech", 1),
    ("a7", "hors-ligne"),
    ("zzz", "eco-tunisie", "invente", 3),  # identifiant inventé par l'IA
)


def redaction(**kw):
    base = {
        "essentiel": [
            {"texte": "La BCT agit sur les taux.", "sujets": ["s1"]},
            {"texte": "La Fed pèse sur les marchés.", "sujets": ["s3", "s99"]},
        ],
        "sujets": [
            {"cle": "s1", "titre": "Taux directeur", "texte": "La BCT relève son taux.", "impact_menage": "Les crédits à taux variable augmentent."},
            {"cle": "s2", "titre": "Dividendes", "texte": "Une société annonce un dividende."},
            {"cle": "s3", "titre": "La Fed", "texte": "La Fed maintient ses taux."},
            {"cle": "s4", "titre": "Fintech", "texte": "Une levée de fonds."},
        ],
        "titres_fr": [{"id": "a4", "titre": "Titre français de a4"}, {"id": "a5", "titre": "Titre français de a5"}],
    }  # fmt: skip
    return {**base, **kw}


def produire(articles=ARTICLES, ia=None, jour=MAINTENANT):
    ia = ia or FauxIa(CLASSEMENT_OK, redaction())
    ident, type_ = fichier_et_id("matin", jour)
    return produire_edition(
        ia=ia,
        articles=articles,
        type_enregistre=type_,
        ident=ident,
        maintenant=jour,
        journal=journal(),
    ), ia


# --- A4 / A5 : contenu de l'édition ------------------------------------------------------


def test_edition_nominale_conforme_au_schema_et_aux_regles_du_paragraphe_4():
    ed, ia = produire()
    valider_edition(ed)  # A5
    assert ed["id"] == "2026-11-17-matin" and ed["version"] == 1 and ed["modele"] == "gemini-test"
    assert len(ia.prompts) == 2  # deux appels IA, pas plus
    # chapitres non vides, dans l'ordre du § 4 ; aucun chapitre vide
    assert [c["cle"] for c in ed["chapitres"]] == [
        "eco-tunisie",
        "bourse-entreprises",
        "international",
        "technologie",
    ]
    # chaque sujet cite au moins un article d'origine existant (A4)
    for c in ed["chapitres"]:
        for s in c["sujets"]:
            assert s["articles"] and all(a in ed["articles"] for a in s["articles"])
    # un fait couvert par deux sources n'apparaît qu'une fois, avec les deux liens
    taux = ed["chapitres"][0]["sujets"][0]
    assert taux["articles"] == ["a2", "a1"] or sorted(taux["articles"]) == ["a1", "a2"]
    assert taux["rubrique"] == "reglementation" and taux["impact_menage"].startswith("Les crédits")
    # l'article hors ligne et l'identifiant inventé n'apparaissent nulle part
    assert "a7" not in ed["articles"] and "zzz" not in json.dumps(ed)
    assert "zzz" not in json.dumps(ed)


def test_aucun_lien_google_news_ni_utm_dans_l_edition():
    ed, _ = produire()
    brut = json.dumps(ed)
    assert "news.google.com" not in brut and "utm_" not in brut


def test_titres_francais_pour_les_articles_non_francophones_et_titre_d_origine_conserve():
    ed, _ = produire()
    a4 = ed["articles"]["a4"]
    assert a4["titre"] == "Titre français de a4" and a4["titre_origine"] == "Titre a4"
    assert a4["url_traduite"] and a4["langue"] == "en"
    assert "titre_origine" not in ed["articles"]["a1"]  # français : pas de titre d'origine
    # source payante : pas de lien traduit
    assert ed["articles"]["a5"]["payant"] is True and ed["articles"]["a5"]["url_traduite"] is None


def test_chiffres_et_tableaux_vides_jusqu_a_v3_donnee_absente_vaut_null():
    ed, _ = produire()
    assert [c["cle"] for c in ed["chiffres"]] == ["tunindex", "eur_tnd_bct", "brent", "tmm"]
    assert all(c["valeur"] is None for c in ed["chiffres"])  # jamais 0
    assert all(c["tableau"] is None for c in ed["chapitres"])


def test_l_essentiel_ignore_les_sujets_inventes_et_cite_les_articles_du_sujet():
    ed, _ = produire()
    assert len(ed["essentiel"]) == 2
    assert sorted(ed["essentiel"][1]["articles"]) == ["a4", "a5"]  # s99 ignoré, s3 = a4 + a5


def test_essentiel_toujours_present_repli_si_l_ia_n_en_donne_pas():
    sans = redaction(essentiel=[{"texte": "x", "sujets": ["s42"]}])
    ed, _ = produire(ia=FauxIa(CLASSEMENT_OK, sans))
    assert 1 <= len(ed["essentiel"]) <= 3 and ed["essentiel"][0]["articles"]
    valider_edition(ed)


def test_au_plus_cinq_sujets_par_chapitre():
    nombreux = [art(f"a{i}") for i in range(1, 9)]
    cl = classement(
        *[(f"a{i}", "eco-tunisie", f"sujet{i}", 1 + i % 3, "presse") for i in range(1, 9)]
    )
    red = {
        "essentiel": [{"texte": "Point", "sujets": ["s1"]}],
        "sujets": [{"cle": f"s{i}", "titre": f"T{i}", "texte": f"X{i}"} for i in range(1, 9)],
    }
    ed, _ = produire(articles=nombreux, ia=FauxIa(cl, red))
    assert len(ed["chapitres"][0]["sujets"]) == 5


def test_sujet_non_redige_par_l_ia_repli_sur_l_article_jamais_de_trou():
    red = redaction(sujets=[{"cle": "s1", "titre": "Seul sujet", "texte": "Texte."}])
    ed, _ = produire(ia=FauxIa(CLASSEMENT_OK, red))
    valider_edition(ed)
    assert all(s["titre"] and s["texte"] for c in ed["chapitres"] for s in c["sujets"])


def test_rien_a_publier_pas_d_edition_vide():
    with pytest.raises(AucuneActualite):
        produire(articles=[])
    tout_hors = classement(("a1", "hors-ligne"), ("a2", "hors-ligne"))
    with pytest.raises(AucuneActualite):
        produire(articles=ARTICLES[:2], ia=FauxIa(tout_hors))


def test_le_prompt_contient_la_ligne_editoriale_et_seulement_des_identifiants_connus():
    _, ia = produire()
    assert "a1 | BCT | fr | eco-tunisie | Titre a1 | Résumé de a1" in ia.prompts[0]
    assert "SUJET s1 | chapitre eco-tunisie | rubrique reglementation" in ia.prompts[1]
    assert "a_traduire : a4, a5" in ia.prompts[1]


# --- A5 : contrat ------------------------------------------------------------------------


def edition_valide():
    return produire()[0]


@pytest.mark.parametrize(
    "mutation, message",
    [
        (
            lambda e: e["articles"]["a1"].update(url="https://news.google.com/rss/articles/xyz"),
            "Google News",
        ),
        (lambda e: e["articles"]["a1"].update(url="https://exemple.tn/a?utm_source=x"), "suivi"),
        (lambda e: e["chapitres"][0]["sujets"][0]["articles"].append("fantome"), "absents"),
        (lambda e: e["chapitres"].reverse(), "désordre"),
        (lambda e: e.update(version=2), "schéma"),
        (lambda e: e.update(id="2026-11-17-nuit"), "schéma"),
        (lambda e: e["chapitres"][0]["sujets"][0].update(articles=[]), "schéma"),
        (lambda e: e["essentiel"].extend(copy.deepcopy(e["essentiel"]) * 3), "schéma"),
        (lambda e: e["articles"]["a1"].update(url="ftp://x"), "schéma"),
    ],
)
def test_contrat_refuse_les_editions_invalides(mutation, message):
    e = edition_valide()
    mutation(e)
    with pytest.raises(EditionInvalide, match=message):
        valider_edition(e)


def test_le_schema_est_celui_du_depot_et_se_charge():
    from veille.edition.modele import charger_schema

    assert charger_schema()["properties"]["version"] == {"const": 1}


# --- fenêtres ---------------------------------------------------------------------------


def lundi(h, m=0):
    return datetime(2026, 11, 16, h - 1, m, tzinfo=UTC)  # heure de Tunis = UTC+1


def test_type_d_edition_attendu():
    assert type_pour(datetime(2026, 11, 17, 6, 30, tzinfo=UTC)) == "matin"
    assert type_pour(datetime(2026, 11, 17, 17, 30, tzinfo=UTC)) == "soir"
    assert type_pour(datetime(2026, 11, 14, 8, 30, tzinfo=UTC)) == "weekend"  # samedi


def test_le_weekend_s_enregistre_comme_matin():
    assert fichier_et_id("weekend", datetime(2026, 11, 14, 8, 30, tzinfo=UTC)) == (
        "2026-11-14-matin",
        "matin",
    )
    assert fichier_et_id("soir", datetime(2026, 11, 13, 17, 30, tzinfo=UTC)) == (
        "2026-11-13-soir",
        "soir",
    )


def test_fenetre_du_matin_depuis_le_soir_precedent():
    hist = [{"id": "2026-11-16-soir", "fin": "2026-11-16T18:30:00+01:00"}]
    debut, fin = calculer_fenetre("matin", MAINTENANT, hist)
    assert debut == datetime.fromisoformat("2026-11-16T18:30:00+01:00") and fin == MAINTENANT


def test_fenetre_du_soir_depuis_le_matin_et_sans_historique():
    soir = datetime(2026, 11, 17, 17, 30, tzinfo=UTC)
    hist = [{"id": "2026-11-17-matin", "fin": "2026-11-17T07:30:00+01:00"}]
    assert calculer_fenetre("soir", soir, hist)[0] == datetime.fromisoformat(
        "2026-11-17T07:30:00+01:00"
    )
    assert calculer_fenetre("soir", soir, [])[0] == soir.replace(
        hour=6, minute=30
    )  # 11 h par défaut


def test_relancer_la_meme_edition_ne_reduit_pas_la_fenetre():
    hist = [
        {"id": "2026-11-16-soir", "fin": "2026-11-16T18:30:00+01:00"},
        {
            "id": "2026-11-17-matin",
            "fin": "2026-11-17T07:30:00+01:00",
        },  # la même édition, déjà produite
    ]
    assert calculer_fenetre("matin", MAINTENANT, hist)[0] == datetime.fromisoformat(
        "2026-11-16T18:30:00+01:00"
    )


def test_fenetre_du_weekend_24_heures_et_plafond():
    sam = datetime(2026, 11, 14, 8, 30, tzinfo=UTC)
    debut, fin = calculer_fenetre("weekend", sam, [])
    assert fin - debut.astimezone(UTC) == (fin - (sam.replace(day=13)))
    ancien = [{"id": "2026-11-10-soir", "fin": "2026-11-10T18:30:00+01:00"}]
    debut, fin = calculer_fenetre("matin", MAINTENANT, ancien)
    assert (fin - debut).total_seconds() == 72 * 3600  # jamais plus de 72 h


def test_charger_articles_selon_vu_le_puis_publie_le(tmp_path):
    etat = EtatLocal(tmp_path)
    lignes = [
        {
            "id": "dedans",
            "vu_le": "2026-11-16T20:00:00+01:00",
            "publie_le": "2026-11-16T00:00:00+01:00",
        },
        {
            "id": "avant",
            "vu_le": "2026-11-16T12:00:00+01:00",
            "publie_le": "2026-11-16T12:00:00+01:00",
        },
        {"id": "sans_vu_le", "publie_le": "2026-11-17T03:00:00+01:00"},
        {
            "id": "apres",
            "vu_le": "2026-11-17T09:00:00+01:00",
            "publie_le": "2026-11-17T09:00:00+01:00",
        },
    ]
    etat.ajouter_lignes("articles/2026-11-16.jsonl", [json.dumps(x) for x in lignes[:2]])
    etat.ajouter_lignes("articles/2026-11-17.jsonl", [json.dumps(x) for x in lignes[2:]])
    debut = datetime.fromisoformat("2026-11-16T18:30:00+01:00")
    ids = [a["id"] for a in charger_articles(etat, debut, MAINTENANT)]
    assert sorted(ids) == ["dedans", "sans_vu_le"]  # « dedans » : vu_le fait foi, pas la date 00:00


def test_classement_renvoye_comme_tableau_seul_est_accepte():
    """Constat réel (Gemini, 14/11) : la liste est renvoyée sans l'objet {"articles": …}."""
    tableau_seul = CLASSEMENT_OK["articles"]
    ed, _ = produire(ia=FauxIa(tableau_seul, redaction()))
    valider_edition(ed)
    assert len(ed["chapitres"]) == 4
