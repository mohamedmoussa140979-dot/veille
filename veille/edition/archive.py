"""Archive HTML (GitHub Pages, spec § 8.3) : une page par édition, un index par mois, recherche.

Pages statiques construites à chaque édition à partir de toutes les éditions de la branche
`data` ; tout texte est échappé. Aucun texte d'article n'est reproduit, aucune image.
"""

from __future__ import annotations

import html
import json
from datetime import date, timedelta
from pathlib import Path

from veille.edition.modele import RUBRIQUES
from veille.marches.formats import date_courte, nombre, signe

NOMS_EDITION = {"matin": "🌅 Matin", "soir": "🌆 Soir"}
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
        "octobre", "novembre", "décembre"]  # fmt: skip
JOURS_RECHERCHE = 30

CSS = """
:root{--fond:#fafafa;--texte:#1a1a1a;--doux:#5c6670;--ligne:#dde1e6;--accent:#0a4d8c;--carte:#fff}
@media (prefers-color-scheme:dark){:root{--fond:#121417;--texte:#e8eaed;--doux:#9aa4af;--ligne:#2c3138;--accent:#7ab7f5;--carte:#1b1f24}}
*{box-sizing:border-box}body{margin:0;background:var(--fond);color:var(--texte);font:16px/1.55 -apple-system,Segoe UI,Roboto,Arial,sans-serif}
main{max-width:760px;margin:0 auto;padding:16px}a{color:var(--accent)}h1{font-size:1.4rem;margin:.2em 0 .6em}
h2{font-size:1.1rem;margin:1.6em 0 .5em;padding-left:.6em;border-left:4px solid var(--accent)}
.meta{color:var(--doux);font-size:.85rem}.carte{background:var(--carte);border:1px solid var(--ligne);border-radius:8px;padding:12px 14px;margin:10px 0}
.sujet h3{font-size:1rem;margin:0 0 .3em}.sujet p{margin:.3em 0}.liens{font-size:.9rem;color:var(--doux)}
.menage{font-size:.92rem;margin:.4em 0}.pastille{font-size:.72rem;border:1px solid var(--ligne);border-radius:4px;padding:0 4px;margin-left:3px;color:var(--doux)}
nav a{margin-right:.8em}input[type=search]{width:100%;padding:10px;font-size:1rem;border:1px solid var(--ligne);border-radius:8px;background:var(--carte);color:var(--texte)}
table.tab{width:100%;border-collapse:collapse;font-size:.92rem}table.tab th,table.tab td{text-align:right;padding:5px 6px;border-bottom:1px solid var(--ligne)}table.tab th:first-child,table.tab td:first-child{text-align:left}
ul.liste{list-style:none;padding:0}ul.liste li{padding:8px 0;border-bottom:1px solid var(--ligne)}
"""

JS_RECHERCHE = """
(function(){var champ=document.getElementById('q'),zone=document.getElementById('resultats'),donnees=null;
function charger(){return donnees?Promise.resolve(donnees):fetch('recherche.json').then(function(r){return r.json()}).then(function(d){donnees=d;return d})}
function norm(t){return t.toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g,'')}
function echapper(t){var d=document.createElement('div');d.textContent=t;return d.innerHTML}
champ.addEventListener('input',function(){var q=norm(champ.value.trim());if(q.length<3){zone.innerHTML='';return}
charger().then(function(d){var m=d.filter(function(e){return norm(e.titre+' '+e.texte).indexOf(q)>=0}).slice(0,40);
zone.innerHTML=m.length?m.map(function(e){return '<li><a href="editions/'+e.id+'.html">'+echapper(e.titre)+'</a><div class="meta">'+echapper(e.date+' · '+e.edition+' · '+e.chapitre)+'</div></li>'}).join(''):'<li class="meta">Aucun résultat sur les 30 derniers jours.</li>'})})})();
"""


def _e(texte) -> str:
    return html.escape(str(texte or ""), quote=True)


def _date_longue(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {MOIS[d.month - 1]} {d.year}"


def _page(titre: str, corps: str, racine: str = "", description: str = "") -> str:
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>{_e(titre)}</title><meta name="description" content="{_e(description)}">
<style>{CSS}</style></head><body><main>
<nav><a href="{racine}index.html">Archive</a></nav>
{corps}
</main></body></html>
"""


def _liens(ids: list[str], articles: dict[str, dict]) -> str:
    morceaux = []
    for i in ids:
        a = articles[i]
        m = f'<a href="{_e(a["url"])}" rel="noopener noreferrer">{_e(a["source"])}</a>'
        if a["langue"] != "fr":
            m += f'<span class="pastille">{_e(a["langue"].upper())}</span>'
        if a.get("url_traduite"):
            m += f' (<a href="{_e(a["url_traduite"])}" rel="noopener noreferrer">FR</a>)'
        if a.get("payant"):
            m += ' <span title="Accès payant">🔒</span>'
        morceaux.append(m)
    return " · ".join(morceaux)


def _libelle(ligne: dict) -> str:
    if ligne.get("source_url"):
        return f'<a href="{_e(ligne["source_url"])}" rel="noopener noreferrer">{_e(ligne["libelle"])}</a>'
    return _e(ligne["libelle"])


def _ligne_tableau(ligne: dict, decimales: int = 2, annee: bool = False) -> str:
    cellules = [
        f"<td>{_libelle(ligne)}</td>",
        f"<td>{_e(nombre(ligne['valeur'], decimales))}</td>",
        f"<td>{_e(signe(ligne.get('variation_pct')))}</td>",
    ]
    if annee:
        cellules.append(f"<td>{_e(signe(ligne.get('variation_annee_pct')))}</td>")
    return "<tr>" + "".join(cellules) + "</tr>"


def tableau_html(chapitre: str, t: dict) -> str:
    """Tableau fixe des chapitres 3 (Bourse) et 4 (marchés internationaux) ; « — » si absent."""
    if chapitre == "bourse-entreprises":
        tete = f"{t['titre']} · séance du {date_courte(t['seance'])}" + (
            " (provisoire)" if t.get("provisoire") else ""
        )
        lignes = "".join(_ligne_tableau(x, annee=True) for x in t["lignes"])
        html_ = (
            f'<div class="carte"><p class="meta">{_e(tete)}</p><table class="tab"><thead><tr>'
            "<th>Indice</th><th>Valeur</th><th>Jour</th><th>Depuis le 1er janvier</th></tr></thead>"
            f"<tbody>{lignes}</tbody></table>"
        )
        for titre, cle in (("Plus fortes hausses", "hausses"), ("Plus fortes baisses", "baisses")):
            if t.get(cle):
                corps = "".join(_ligne_tableau(x, 3) for x in t[cle])
                html_ += (
                    f'<p class="meta">{titre}</p><table class="tab"><tbody>{corps}</tbody></table>'
                )
        return html_ + "</div>"
    lignes = "".join(
        _ligne_tableau(x, 4 if x["cle"] in ("eurusd", "eur_tnd", "usd_tnd") else 2)
        for x in t["lignes"]
    )
    return (
        f'<div class="carte"><p class="meta">{_e(t["titre"])}</p><table class="tab"><thead><tr>'
        "<th>Instrument</th><th>Valeur</th><th>Variation</th></tr></thead>"
        f"<tbody>{lignes}</tbody></table></div>"
    )


def page_edition(ed: dict) -> str:
    articles = ed["articles"]
    corps = [
        f"<h1>{NOMS_EDITION[ed['edition']]} · {_e(_date_longue(ed['date']))}</h1>",
        f'<p class="meta">Généré le {_e(ed["genere_le"])} · modèle {_e(ed["modele"])}</p>',
        "<h2>L'essentiel</h2>",
    ]
    for p in ed["essentiel"]:
        corps.append(
            f'<div class="carte"><p>{_e(p["texte"])}</p>'
            f'<div class="liens">{_liens(p["articles"], articles)}</div></div>'
        )
    for c in ed["chapitres"]:
        corps.append(f"<h2>{_e(c['titre'])}</h2>")
        if c.get("tableau"):
            corps.append(tableau_html(c["cle"], c["tableau"]))
        for s in c["sujets"]:
            rub = RUBRIQUES.get(s.get("rubrique") or "")
            etiquette = f' <span class="pastille">{_e(rub)}</span>' if rub else ""
            menage = (
                f'<p class="menage">🏠 {_e(s["impact_menage"])}</p>'
                if s.get("impact_menage")
                else ""
            )
            corps.append(
                f'<div class="carte sujet"><h3>{_e(s["titre"])}{etiquette}</h3>'
                f"<p>{_e(s['texte'])}</p>{menage}"
                f'<div class="liens">{_liens(s["articles"], articles)}</div></div>'
            )
    return _page(f"Veille {ed['date']} {ed['edition']}", "\n".join(corps), racine="../")


def _liste_editions(editions: list[dict], prefixe: str) -> str:
    lignes = [
        f'<li><a href="{prefixe}editions/{_e(e["id"])}.html">{_e(_date_longue(e["date"]))} · '
        f"{NOMS_EDITION[e['edition']]}</a>"
        f'<div class="meta">{_e(e["essentiel"][0]["texte"][:140])}</div></li>'
        for e in editions
    ]
    return '<ul class="liste">' + "".join(lignes) + "</ul>"


def _tri(editions: list[dict]) -> list[dict]:
    return sorted(editions, key=lambda e: (e["date"], e["edition"] == "soir"), reverse=True)


def entrees_recherche(editions: list[dict], aujourdhui: date) -> list[dict]:
    """Sujets des 30 derniers jours (recherche simple côté client)."""
    limite = (aujourdhui - timedelta(days=JOURS_RECHERCHE)).isoformat()
    entrees = []
    for e in editions:
        if e["date"] < limite:
            continue
        for c in e["chapitres"]:
            for s in c["sujets"]:
                entrees.append(
                    {"id": e["id"], "date": e["date"], "edition": e["edition"],
                     "chapitre": c["titre"], "titre": s["titre"], "texte": s["texte"]}
                )  # fmt: skip
    return entrees


def construire_site(editions: list[dict], sortie: Path, aujourdhui: date) -> list[Path]:
    """Écrit le site statique dans `sortie` ; renvoie les fichiers écrits."""
    sortie = Path(sortie)
    editions = _tri(editions)
    ecrits: list[Path] = []

    def ecrire(chemin: str, contenu: str) -> None:
        f = sortie / chemin
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(contenu, encoding="utf-8", newline="\n")
        ecrits.append(f)

    for e in editions:
        ecrire(f"editions/{e['id']}.html", page_edition(e))

    par_mois: dict[str, list[dict]] = {}
    for e in editions:
        par_mois.setdefault(e["date"][:7], []).append(e)
    for mois, liste in par_mois.items():
        annee, m = mois.split("-")
        titre = f"{MOIS[int(m) - 1].capitalize()} {annee}"
        corps = f"<h1>{_e(titre)}</h1>{_liste_editions(liste, '../')}"
        ecrire(f"{mois}/index.html", _page(f"Veille · {titre}", corps, racine="../"))

    mois_liens = " · ".join(
        f'<a href="{m}/index.html">{_e(MOIS[int(m[5:]) - 1].capitalize())} {_e(m[:4])}</a>'
        for m in sorted(par_mois, reverse=True)
    )
    corps = (
        "<h1>Veille économique</h1>"
        '<p class="meta">Synthèses du matin et du soir (Tunisie, Afrique, international).</p>'
        '<input type="search" id="q" placeholder="Rechercher (30 derniers jours)" aria-label="Recherche">'
        '<ul class="liste" id="resultats"></ul>'
        f"<h2>Dernières éditions</h2>{_liste_editions(editions[:14], '')}"
        f"<h2>Par mois</h2><p>{mois_liens or 'Aucune édition.'}</p>"
        f"<script>{JS_RECHERCHE}</script>"
    )
    ecrire("index.html", _page("Veille économique", corps))
    ecrire(
        "recherche.json", json.dumps(entrees_recherche(editions, aujourdhui), ensure_ascii=False)
    )
    return ecrits
