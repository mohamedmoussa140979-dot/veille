"""Prompts et schémas de sortie des deux appels IA d'une édition (spec § 3, § 4, § 7)."""

from __future__ import annotations

from veille.edition.modele import CHAPITRES, RUBRIQUES

LIGNE_EDITORIALE = """Tu rédiges la veille économique d'un cadre de la banque de financement et d'investissement \
d'une grande banque tunisienne. Tu écris en français.

LIGNE ÉDITORIALE
- Gardé : économie, finance, réglementation, entreprises et acteurs économiques (cotés ou non), \
marchés, technologie à fort impact sur les économies, les entreprises ou les ménages.
- Exclu : sport, arts et culture, guerres et conflits, politique, faits divers, catastrophes \
naturelles, people, santé grand public. Un article exclu reçoit le chapitre « hors-ligne ».
- Cas limite : un fait politique ou un conflit à effet économique direct (loi de finances, droits \
de douane, sanctions, choc pétrolier) est GARDÉ et traité sous l'angle économique.

CHAPITRES
- eco-tunisie : Économie tunisienne. Quatre rubriques : reglementation (circulaires BCT, JORT, \
textes fiscaux, réglementation CMF) ; notations (Fitch, Moody's, S&P, R&I : souverain et banques) ; \
statistiques (INS : croissance, inflation, chômage, commerce extérieur ; indicateurs BCT ; budget, \
loi de finances) ; presse (revue de la presse économique, y compris l'actualité bancaire non cotée).
- bourse-entreprises : Bourse, entreprises et acteurs économiques : communiqués CMF, avis BVMT, \
publications des sociétés cotées (indicateurs trimestriels, états financiers, AGO et dividendes, \
augmentations de capital, emprunts obligataires), actualité de tout acteur économique.
- international : Économie et marchés internationaux : Fed, BCE, données macro majeures, marchés, \
matières premières.
- afrique : Économie africaine : Maghreb (Maroc, Algérie, Libye), Afrique subsaharienne, \
institutions (BAD, Afreximbank, FMI Afrique), ZLECAf.
- technologie : IA, fintech et paiements, cybersécurité, télécoms, énergie et climat sous l'angle \
économique, startups tunisiennes. Seulement avec un impact économique explicite.
"""

CONSIGNE_CLASSEMENT = """Tu reçois une liste d'articles (identifiant | source | langue | chapitre \
suggéré | titre | résumé). Pour chaque article RETENU, donne son chapitre, sa rubrique (seulement pour \
eco-tunisie, sinon null), un identifiant de sujet et une importance de 1 (secondaire) à 3 (majeur).

RÈGLES
- Un fait couvert par plusieurs sources reçoit le MÊME identifiant de sujet (un mot ou deux, en \
minuscules et tirets) ; des faits différents reçoivent des identifiants différents.
- Les articles hors ligne éditoriale reçoivent le chapitre « hors-ligne ». Tu peux aussi les omettre.
- N'invente aucun identifiant : utilise uniquement ceux de la liste.
- Réponds uniquement par UN OBJET JSON de cette forme (pas un tableau seul) :
{"articles": [{"id": "a1b2c3", "chapitre": "eco-tunisie", "rubrique": "presse", "sujet": "taux-directeur", "importance": 2}]}"""

CONSIGNE_REDACTION = """Tu reçois des SUJETS déjà classés par chapitre, avec leurs articles (identifiant, \
source, titre, résumé). Rédige la synthèse.

RÈGLES
- Pour chaque sujet : un titre court et 1 à 2 phrases rédigées par toi, factuelles, sans superlatif ni \
remplissage. Reformule : aucune phrase recopiée d'un article. N'écris aucune information absente des \
articles fournis, ni aucun chiffre qui n'y figure pas.
- Pour les sujets eco-tunisie qui s'y prêtent seulement, une ligne « impact_menage » concrète (par \
exemple « TMM +0,25 pt : les crédits à taux variable augmentent »), sinon null.
- « essentiel » : 3 à 5 points, tous chapitres confondus, du plus important au moins important ; chaque \
point cite les clés des sujets (« sujets ») qu'il résume. Il y a toujours un essentiel.
- Pour chaque article non francophone listé dans « a_traduire », donne son titre en français \
(« titres_fr »), fidèle au titre d'origine.
- Tu cites uniquement les clés de sujets et les identifiants d'articles fournis.
- Réponds uniquement par UN OBJET JSON de cette forme :
{"essentiel": [{"texte": "…", "sujets": ["s1", "s2"]}],
 "sujets": [{"cle": "s1", "titre": "…", "texte": "…", "impact_menage": null}],
 "titres_fr": [{"id": "a1b2c3", "titre": "…"}]}"""

_CLES = [c for c, _ in CHAPITRES]

SCHEMA_CLASSEMENT = {
    "type": "object",
    "required": ["articles"],
    "properties": {
        "articles": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "chapitre"],
                "properties": {
                    "id": {"type": "string"},
                    "chapitre": {"enum": [*_CLES, "hors-ligne"]},
                    "rubrique": {"enum": [*RUBRIQUES, None]},
                    "sujet": {"type": ["string", "null"]},
                    "importance": {"type": ["integer", "null"], "minimum": 1, "maximum": 3},
                },
            },
        }
    },
}

SCHEMA_REDACTION = {
    "type": "object",
    "required": ["essentiel", "sujets"],
    "properties": {
        "essentiel": {
            "type": "array",
            "minItems": 1,
            "maxItems": 5,
            "items": {
                "type": "object",
                "required": ["texte", "sujets"],
                "properties": {
                    "texte": {"type": "string"},
                    "sujets": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "sujets": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["cle", "titre", "texte"],
                "properties": {
                    "cle": {"type": "string"},
                    "titre": {"type": "string"},
                    "texte": {"type": "string"},
                    "impact_menage": {"type": ["string", "null"]},
                },
            },
        },
        "titres_fr": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "titre"],
                "properties": {"id": {"type": "string"}, "titre": {"type": "string"}},
            },
        },
    },
}


def normaliser_classement(donnees):
    """Gemini renvoie parfois la liste seule : on la remet dans l'objet attendu."""
    return {"articles": donnees} if isinstance(donnees, list) else donnees


def _court(texte: str, n: int) -> str:
    texte = " ".join((texte or "").split())
    return texte if len(texte) <= n else texte[: n - 1].rstrip() + "…"


def prompt_classement(articles: list[dict]) -> str:
    lignes = [
        f"{a['id']} | {a['source']} | {a['langue']} | {a.get('chapitre', '')} | "
        f"{_court(a['titre'], 160)} | {_court(a.get('resume', ''), 160)}"
        for a in articles
    ]
    return f"{CONSIGNE_CLASSEMENT}\n\nARTICLES ({len(articles)}) :\n" + "\n".join(lignes)


def prompt_redaction(sujets: list[dict], articles: dict[str, dict], a_traduire: list[str]) -> str:
    blocs = []
    for s in sujets:
        entete = f"SUJET {s['cle']} | chapitre {s['chapitre']}"
        if s.get("rubrique"):
            entete += f" | rubrique {s['rubrique']}"
        corps = [
            f"  - {i} | {articles[i]['source']} | {_court(articles[i]['titre'], 200)} | "
            f"{_court(articles[i].get('resume', ''), 300)}"
            for i in s["articles"]
        ]
        blocs.append(entete + "\n" + "\n".join(corps))
    liste = ", ".join(a_traduire) if a_traduire else "aucun"
    return f"{CONSIGNE_REDACTION}\n\na_traduire : {liste}\n\n" + "\n\n".join(blocs)
