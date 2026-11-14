# État du chantier — dépôt `veille`

Dernière mise à jour : 14/11/2026

**V0 — socle : clos** (bilan : `V0-bilan.md`).
**V1 — collecte et alertes : clos** (fusionné dans `main`, essai réel vert ; bilan : `V1-bilan.md`). La collecte tourne désormais aux horaires du § 5 de la spec. Restent à constater par le porteur : le rendu des alertes d'essai sur le téléphone et la première vraie alerte BCT ou CMF.

**V2 — synthèses : clos** (fusionné dans `main`, essai réel vert ; bilan : `V2-bilan.md`). Les éditions tournent aux horaires du § 5.

**Phase 2 possible** : le fichier d'édition (`schema/edition.v1.json`) est livré et valide sur la branche `data` (`editions/`). La phase 2 (Actualités dans Mizeniti) se lance dans `pfm-platform` avec son propre prompt.

**Lot en cours : V3 — marchés** (inventaire à écrire).

## Lots

| Lot | État |
|---|---|
| V0 socle | clos |
| V1 collecte et alertes | clos |
| V2 synthèses | clos |
| V3 marchés | en cours |
| V4 AWB | à faire |
| V5 santé et bascule | à faire |

## Points ouverts à connaître

- Finextra répond 403 aux serveurs GitHub : anomalie visible dans `sante/` sur `data` ; même blocage attendu pour V4 (AWB).
- `translate.goog` répond 400 pour Reuters et MarketWatch : pas de lien « FR » pour ces deux hôtes.
- `ilboursa` et Tustex gardés comme sources d'articles (à confirmer par le porteur).
- MarketWatch remplace WSJ ; flux orienté finance personnelle, à filtrer par le classement IA.
