import json

import pytest

from tests.conftest import FausseReponse, FauxClient
from veille.ia import (
    Claude,
    CompteurEtat,
    CompteurMemoire,
    ErreurIa,
    Gemini,
    Ia,
    PlafondAtteint,
    classer_modeles,
)
from veille.journal import Journal

MOIS = "2026-11"


def journal():
    return Journal(sortie=lambda _: None)


def liste_modeles(*noms):
    return FausseReponse(
        200,
        json_={
            "models": [
                {"name": f"models/{n}", "supportedGenerationMethods": ["generateContent"]}
                for n in noms
            ]
        },
    )


def gemini_ok(texte="réponse"):
    return FausseReponse(200, json_={"candidates": [{"content": {"parts": [{"text": texte}]}}]})


def gemini(scenario, **kw):
    c = FauxClient(scenario)
    pauses = []
    g = Gemini("CLE-GEMINI-SECRETE", c, journal(), sleep=pauses.append, **kw)
    return g, c, pauses


# --- découverte et classement des modèles Gemini ----------------------------------------


def test_classement_des_modeles():
    noms = [
        "gemini-2.5-flash",
        "gemini-3-flash",
        "gemini-3-flash-preview",
        "gemini-flash-latest",
        "gemini-3-flash-lite",
        "gemini-2.5-flash-image",
        "gemini-3-pro",
        "text-embedding-004",
        "gemma-3-27b",
        "gemini-2.5-flash-preview-tts",
    ]
    assert classer_modeles(noms) == [
        "gemini-flash-latest",
        "gemini-3-flash",
        "gemini-2.5-flash",
        "gemini-3-flash-preview",
        "gemini-3-flash-lite",
    ]


def test_decouverte_filtre_generateContent_et_suit_la_pagination():
    p1 = FausseReponse(
        200,
        json_={
            "models": [
                {
                    "name": "models/gemini-3-flash",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {"name": "models/embed-flash", "supportedGenerationMethods": ["embedContent"]},
            ],
            "nextPageToken": "page2",
        },
    )
    p2 = liste_modeles("gemini-2.5-flash")
    g, c, _ = gemini([p1, p2])
    assert g.modeles() == ["gemini-3-flash", "gemini-2.5-flash"]
    assert c.appels[1]["params"]["pageToken"] == "page2"
    g.modeles()  # en cache : aucun nouvel appel
    assert len(c.appels) == 2


def test_decouverte_en_panne_repli_sur_l_alias_latest():
    g, _, _ = gemini([FausseReponse(500)])
    assert g.modeles() == ["gemini-flash-latest"]


# --- génération Gemini ------------------------------------------------------------------


def test_generation_cle_dans_l_en_tete_pas_dans_l_url():
    g, c, _ = gemini([liste_modeles("gemini-3-flash"), gemini_ok("bonjour")])
    texte, modele = g.generer("salut", json_mode=True)
    assert (texte, modele) == ("bonjour", "gemini-3-flash")
    appel = c.appels[1]
    assert "CLE-GEMINI-SECRETE" not in appel["url"]
    assert appel["headers"]["x-goog-api-key"] == "CLE-GEMINI-SECRETE"
    assert appel["url"].endswith("/models/gemini-3-flash:generateContent")
    assert appel["json"]["generationConfig"]["responseMimeType"] == "application/json"
    assert appel["json"]["contents"][0]["parts"][0]["text"] == "salut"


def test_503_sur_un_modele_essai_du_suivant():
    g, c, pauses = gemini(
        [liste_modeles("gemini-3-flash", "gemini-2.5-flash"), FausseReponse(503), gemini_ok("ok")]
    )
    assert g.generer("x") == ("ok", "gemini-2.5-flash")
    assert pauses == []


def test_tous_les_modeles_en_surcharge_pauses_croissantes_puis_echec():
    scenario = [liste_modeles("gemini-3-flash", "gemini-2.5-flash")] + [FausseReponse(503)] * 6
    g, c, pauses = gemini(scenario, attentes=(10, 30))
    with pytest.raises(ErreurIa):
        g.generer("x")
    assert pauses == [10, 30]  # trois tours, deux pauses
    assert len(c.appels) == 1 + 3 * 2


def test_succes_apres_une_pause():
    g, _, pauses = gemini(
        [liste_modeles("gemini-3-flash"), FausseReponse(429), gemini_ok("enfin")], attentes=(5,)
    )
    assert g.generer("x") == ("enfin", "gemini-3-flash")
    assert pauses == [5]


def test_modele_introuvable_est_ecarte_aux_tours_suivants():
    scenario = [
        liste_modeles("gemini-3-flash", "gemini-2.5-flash"),
        FausseReponse(404),  # tour 1, modèle 1
        FausseReponse(503),  # tour 1, modèle 2
        gemini_ok("ok"),  # tour 2 : seul le modèle 2 est réessayé
    ]
    g, c, _ = gemini(scenario, attentes=(1,))
    assert g.generer("x") == ("ok", "gemini-2.5-flash")
    assert len(c.appels) == 4


def test_cle_refusee_arret_immediat_sans_pause():
    refus = FausseReponse(
        400, json_={"error": {"message": "API key not valid."}}, texte="API key not valid"
    )
    g, c, pauses = gemini([liste_modeles("gemini-3-flash", "gemini-2.5-flash"), refus])
    with pytest.raises(ErreurIa, match="clé"):
        g.generer("x")
    assert len(c.appels) == 2 and pauses == []


def test_reponse_vide_ou_bloquee_passe_au_modele_suivant():
    vide = FausseReponse(200, json_={"candidates": [{"finishReason": "SAFETY"}]})
    g, _, _ = gemini([liste_modeles("gemini-3-flash", "gemini-2.5-flash"), vide, gemini_ok("ok")])
    assert g.generer("x") == ("ok", "gemini-2.5-flash")


def test_les_blocs_de_reflexion_ne_sont_pas_dans_le_texte():
    r = FausseReponse(
        200,
        json_={
            "candidates": [
                {"content": {"parts": [{"text": "pensée", "thought": True}, {"text": "réponse"}]}}
            ]
        },
    )
    g, _, _ = gemini([liste_modeles("gemini-3-flash"), r])
    assert g.generer("x")[0] == "réponse"


# --- Claude : secours, coût, plafond ----------------------------------------------------


def reponse_claude(texte="ok", entree=1000, sortie=500, arret="end_turn"):
    return FausseReponse(
        200,
        json_={
            "content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": texte}],
            "stop_reason": arret,
            "usage": {"input_tokens": entree, "output_tokens": sortie},
        },
    )


def claude(scenario, compteur=None, plafond=5.0, **kw):
    c = FauxClient(scenario)
    compteur = compteur if compteur is not None else CompteurMemoire()
    cl = Claude(
        "CLE-CLAUDE-SECRETE",
        c,
        compteur,
        journal(),
        modele="claude-sonnet-5-5",
        prix_entree=2.0,
        prix_sortie=10.0,
        plafond_usd=plafond,
        mois=lambda: MOIS,
        **kw,
    )
    return cl, c, compteur


def test_claude_requete_et_cout():
    cl, c, compteur = claude([reponse_claude("bonjour", entree=100_000, sortie=20_000)])
    res = cl.generer("prompt", systeme="consigne")
    assert (
        res.texte == "bonjour" and res.fournisseur == "claude" and res.modele == "claude-sonnet-5-5"
    )
    appel = c.appels[0]
    assert appel["url"] == "https://api.anthropic.com/v1/messages"
    assert appel["headers"]["x-api-key"] == "CLE-CLAUDE-SECRETE"
    assert appel["headers"]["anthropic-version"] == "2023-06-01"
    corps = appel["json"]
    assert corps["model"] == "claude-sonnet-5-5" and corps["system"] == "consigne"
    assert corps["messages"] == [{"role": "user", "content": "prompt"}]
    assert not {"temperature", "top_p", "top_k"} & set(corps)
    # 100 000 × 2 $/M + 20 000 × 10 $/M = 0,20 + 0,20
    assert compteur.depense(MOIS) == pytest.approx(0.40)


def test_a7_plafond_atteint_aucune_requete_claude():
    compteur = CompteurMemoire()
    compteur.ajouter(MOIS, 5.0, 0, 0)
    cl, c, _ = claude([], compteur=compteur)  # aucun appel HTTP attendu
    with pytest.raises(PlafondAtteint):
        cl.generer("x")
    assert c.appels == []


def test_plafond_borne_haute_de_l_appel_comprise():
    compteur = CompteurMemoire()
    compteur.ajouter(MOIS, 4.95, 0, 0)  # reste 0,05 $ ; l'appel peut coûter jusqu'à ~0,08 $
    cl, c, _ = claude([], compteur=compteur, max_tokens=8000)
    with pytest.raises(PlafondAtteint):
        cl.generer("court")
    assert c.appels == []


def test_un_nouveau_mois_remet_le_compteur_a_zero():
    compteur = CompteurMemoire()
    compteur.ajouter("2026-10", 5.0, 0, 0)
    cl, _, _ = claude([reponse_claude()], compteur=compteur)
    assert cl.generer("x").texte == "ok"


def test_refus_de_securite_est_une_erreur_mais_reste_facture():
    cl, _, compteur = claude([reponse_claude("", 1000, 10, arret="refusal")])
    with pytest.raises(ErreurIa, match="refus"):
        cl.generer("x")
    assert compteur.depense(MOIS) > 0


def test_erreur_http_claude():
    cl, _, compteur = claude([FausseReponse(529, json_={"error": {"message": "surcharge"}})])
    with pytest.raises(ErreurIa, match="529"):
        cl.generer("x")
    assert compteur.depense(MOIS) == 0


# --- compteur persistant ----------------------------------------------------------------


class FauxEtat:
    def __init__(self):
        self.d = {}

    def lire_json(self, chemin, defaut=None):
        return self.d.get(chemin, defaut)

    def modifier_json(self, chemin, fonction, *, defaut, message=None):
        self.d[chemin] = fonction(self.d.get(chemin, defaut))
        return True


def test_compteur_etat_persiste_par_mois():
    etat = FauxEtat()
    cpt = CompteurEtat(etat)
    cpt.ajouter(MOIS, 0.5, 1000, 200)
    cpt.ajouter(MOIS, 0.25, 500, 100)
    assert cpt.depense(MOIS) == pytest.approx(0.75)
    assert etat.d["state/claude.json"][MOIS]["appels"] == 2
    assert CompteurEtat(etat).depense("2026-12") == 0


# --- orchestrateur ----------------------------------------------------------------------


def test_gemini_suffit_claude_non_sollicite():
    g, _, _ = gemini([liste_modeles("gemini-3-flash"), gemini_ok("de Gemini")])
    cl, cc, _ = claude([])
    res = Ia(g, cl, journal()).generer("x")
    assert (res.texte, res.fournisseur) == ("de Gemini", "gemini")
    assert cc.appels == []


def test_a7_gemini_en_echec_claude_prend_le_relais():
    g, _, _ = gemini(
        [liste_modeles("gemini-3-flash")] + [FausseReponse(503)] * 4, attentes=(1, 1, 1)
    )
    cl, cc, _ = claude([reponse_claude("de Claude")])
    j = journal()
    res = Ia(g, cl, j).generer("x")
    assert (res.texte, res.fournisseur) == ("de Claude", "claude")
    codes = [e["code"] for e in j.evenements]
    assert "gemini_echec" in codes and "claude_secours_utilise" in codes


def test_a7_plafond_atteint_pas_de_requete_alerte_sante():
    g, _, _ = gemini(
        [liste_modeles("gemini-3-flash")] + [FausseReponse(503)] * 4, attentes=(1, 1, 1)
    )
    compteur = CompteurMemoire()
    compteur.ajouter(MOIS, 5.0, 0, 0)
    cl, cc, _ = claude([], compteur=compteur)
    j = journal()
    with pytest.raises(ErreurIa):
        Ia(g, cl, j).generer("x")
    assert cc.appels == []
    assert [
        e for e in j.evenements if e["code"] == "claude_plafond_atteint" and e["niveau"] == "erreur"
    ]


def test_sans_cle_claude_l_echec_gemini_remonte():
    g, _, _ = gemini(
        [liste_modeles("gemini-3-flash")] + [FausseReponse(503)] * 4, attentes=(1, 1, 1)
    )
    with pytest.raises(ErreurIa):
        Ia(g, None, journal()).generer("x")


SCHEMA = {
    "type": "object",
    "required": ["essentiel"],
    "properties": {"essentiel": {"type": "array", "items": {"type": "string"}}},
}


def test_json_valide_dans_des_balises_de_code():
    g, _, _ = gemini(
        [liste_modeles("gemini-3-flash"), gemini_ok('```json\n{"essentiel": ["a"]}\n```')]
    )
    res = Ia(g, None, journal()).generer_json("x", SCHEMA)
    assert res.donnees == {"essentiel": ["a"]}


def test_json_invalide_un_nouvel_essai_puis_succes():
    g, c, _ = gemini(
        [liste_modeles("gemini-3-flash"), gemini_ok("pas du json"), gemini_ok('{"essentiel": []}')]
    )
    res = Ia(g, None, journal()).generer_json("x", SCHEMA)
    assert res.donnees == {"essentiel": []} and res.essais == 2
    second_prompt = c.appels[-1]["json"]["contents"][0]["parts"][0]["text"]
    assert second_prompt.startswith("x") and "JSON valide" in second_prompt


def test_json_non_conforme_au_schema_deux_fois_echec_propre():
    g, _, _ = gemini(
        [
            liste_modeles("gemini-3-flash"),
            gemini_ok('{"autre": 1}'),
            gemini_ok('{"essentiel": "x"}'),
        ]
    )
    with pytest.raises(ErreurIa, match="JSON"):
        Ia(g, None, journal()).generer_json("x", SCHEMA)


def test_aucun_secret_dans_les_evenements():
    j = Journal(sortie=lambda _: None)
    j.enregistrer_secret("CLE-GEMINI-SECRETE")
    c = FauxClient(
        [
            liste_modeles("gemini-3-flash"),
            FausseReponse(400, texte="API key CLE-GEMINI-SECRETE invalide"),
        ]
    )
    g = Gemini("CLE-GEMINI-SECRETE", c, j, sleep=lambda _: None)
    with pytest.raises(ErreurIa) as e:
        g.generer("x")
    assert "CLE-GEMINI-SECRETE" not in str(e.value)
    assert "CLE-GEMINI-SECRETE" not in json.dumps(j.evenements)


def test_normaliser_corrige_une_forme_equivalente_sans_nouvel_essai():
    g, c, _ = gemini([liste_modeles("gemini-3-flash"), gemini_ok('[{"id": "a1"}]')])
    schema = {
        "type": "object",
        "required": ["articles"],
        "properties": {"articles": {"type": "array"}},
    }
    res = Ia(g, None, journal()).generer_json(
        "x", schema, normaliser=lambda d: {"articles": d} if isinstance(d, list) else d
    )
    assert res.donnees == {"articles": [{"id": "a1"}]} and res.essais == 1


def test_message_d_erreur_de_schema_court_sans_recopier_la_donnee():
    enorme = json.dumps({"autre": ["x" * 50] * 200})
    g, c, _ = gemini([liste_modeles("gemini-3-flash"), gemini_ok(enorme), gemini_ok(enorme)])
    j = journal()
    with pytest.raises(ErreurIa) as e:
        Ia(g, None, j).generer_json("x", SCHEMA)
    assert len(str(e.value)) < 200 and "xxxxx" not in str(e.value)
    second_prompt = c.appels[-1]["json"]["contents"][0]["parts"][0]["text"]
    assert (
        len(second_prompt) < 400 and "xxxxx" not in second_prompt
    )  # la demande de reprise reste courte
