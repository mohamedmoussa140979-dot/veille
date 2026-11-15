# État du chantier — dépôt `veille`

Dernière mise à jour : 15/11/2026

## Lots

| Lot | État | Bilan |
|---|---|---|
| V0 socle | clos | `V0-bilan.md` |
| V1 collecte et alertes | clos | `V1-bilan.md` |
| V2 synthèses | clos | `V2-bilan.md` |
| V3 marchés | clos | `V3-bilan.md` |
| V4 AWB | clos | `V4-bilan.md` |
| V5 santé et bascule | **clos, sauf le bilan de la première semaine** (voir ci-dessous) | `V5-bilan.md` |

Tout tourne sur GitHub Actions aux horaires de la spec § 5 : `collecte`, `edition`, `marches`, `awb`, `sante`. Archive : https://mohamedmoussa140979-dot.github.io/veille/

**Phase 2 possible** : le fichier d'édition (`schema/edition.v1.json`) est livré et valide sur la branche `data` (`editions/`). La phase 2 (Actualités dans Mizeniti) se lance dans `pfm-platform` avec son propre prompt.

## À faire après sept jours de fonctionnement réel (à partir du 22/11/2026)

1. **Bilan de la semaine** (`docs/bilans/SEMAINE1-bilan.md`) : éditions produites, alertes envoyées, sources muettes, consommation Claude, anomalies de santé, faux positifs. Sources : `editions/`, `state/alertes_stats.json`, `state/claude.json`, `sante/2026-11.jsonl` sur la branche `data`.
2. **Rappel au porteur** : archiver lui-même `sitemoussam`, `veille-bfi`, `veille-awb`, `veille-tunisie` (Settings → Archive). Claude Code ne supprime ni n'archive aucun dépôt.

## Points ouverts à connaître

- **À constater sur le téléphone** : les messages d'essai (alertes, 🌅, 📈, 🏦, ⚠️), voir la section « À regarder sur le téléphone » de chaque bilan.
- **Finextra** répond 403 aux serveurs GitHub et **GDELT** 429 (espacement passé à 8 s) : le sujet technologique de la veille AWB peut rester vide ; le contrôle de santé le signalera.
- **`translate.goog`** répond 400 pour Reuters et MarketWatch : pas de lien « FR » pour ces deux hôtes.
- **MASI** : aucune source (pas de symbole Yahoo) ; ligne affichée avec un tiret.
- **Fiche BVMT par valeur** introuvable : les lignes du tableau de Bourse renvoient vers la liste des émetteurs.
- **Pas de repli direct** sur le site de la Bourse : Mizeniti est la seule source de Bourse et de taux BCT.
- **`ilboursa` et Tustex** gardés comme sources d'articles de presse (liste validée V28), à confirmer par le porteur.
- **Politique** : filtrée par le classement de l'IA, pas par mots (cas limite à surveiller).
- **Fêtes religieuses mobiles** à ajouter dans `config/jours_feries.yaml` chaque année.
- **R&I** (agence japonaise du § 4 de la spec) : aucune source dans les anciens scripts, non ajoutée.
