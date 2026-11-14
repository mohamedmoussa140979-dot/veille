# État du chantier — dépôt `veille`

Dernière mise à jour : 14/11/2026

**Lot en cours : V0 — socle** (fusionné dans `main`). **Arrêt : essai réel Telegram en échec (« chat not found »), en attente du porteur.** Bilan : `V0-bilan.md`.

## Changements du lot V0

| # | Changement | État |
|---|---|---|
| 1 | Squelette : `pyproject`, dépendances épinglées, `.gitignore`, `.gitattributes`, `config/` | fait |
| 2 | `journal` (masquage des secrets, événements), `temps` (heure de Tunis) | fait |
| 3 | `http` (délais, nouveaux essais, en-têtes, encodage des URL) | fait |
| 4 | `telegram` (en-têtes, découpage, repli texte brut) — A6 | fait |
| 5 | `etat` (branche `data`, transactions, reprise sur conflit) — A9 | fait |
| 6 | `ia` (Gemini → Claude, plafond, compteur, JSON validé) — A7 | fait |
| 7 | `config` (chargement + validation) ; tests du dépôt (rien sur `main`, scan de secrets) — A9, A10 | fait |
| 8 | Workflows `tests` (sur push) et `smoke` (manuel), README | fait |
| 9 | CI verte sur un vrai runner (hypothèse H5) | fait |
| 10 | Fusion dans `main`, essai réel `smoke`, bilan | fait, sauf Telegram (H3) : à rejouer après correction |

## Lots suivants

V1 collecte et alertes · V2 synthèses · V3 marchés · V4 AWB · V5 santé et bascule.
