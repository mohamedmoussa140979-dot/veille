# Bilan — V0 socle — 14/11/2026

## En une phrase
Le socle (HTTP, Telegram, IA Gemini puis Claude, état sur `data`, journal, configuration) est livré, testé et fusionné dans `main` ; l'essai réel est vert partout sauf Telegram, qui répond « chat not found » : c'est le seul point ouvert.

## Fait
- Module commun `veille/` : `http`, `telegram`, `ia`, `etat`, `journal`, `temps`, `config`, plus `smoke` (essai réel).
- Configuration : `config/parametres.yaml`, `sources.yaml` (vide jusqu'à V1), `exclusions.yaml` (vide jusqu'à V1).
- CI de tests sur `push` (sans cron) ; workflow manuel `smoke` ; README d'exploitation.
- Branche `data` créée par le code lors du premier essai.
- 84 tests, sans réseau (garde-fou dans `tests/conftest.py`).

## Vérifié, et comment
| Critère | Commande ou contrôle | Résultat |
|---|---|---|
| A6 — message de plus de 4 096 caractères découpé sans balise cassée | `tests/test_telegram.py` : cas ciblés (balise qui traverse la coupure, mot géant, entités, limite exacte) + 60 messages aléatoires à graine fixe, tous contrôlés (taille, équilibre des balises, texte conservé) | Vert |
| A7 — Gemini en échec → Claude ; plafond atteint → aucune requête Claude + alerte santé | `tests/test_ia.py` : relais Claude, plafond atteint (aucun appel HTTP), borne haute de l'appel comprise, nouveau mois, refus de sécurité facturé | Vert |
| A9 — aucune donnée sur `main` | `tests/test_depot.py` (structure, dossiers de données, taille) + contrôle réel : `git ls-tree origin/main` sans `state/`, `sante/`, `articles/` | Vert |
| A9 — aucune écriture concurrente perdue sur `data` | `tests/test_etat.py` : deux tâches simultanées (vrais dépôts Git locaux), conflit forcé en cours de transaction, poussée refusée par le dépôt | Vert |
| A10 — aucun secret, e-mail ou identifiant personnel | `tests/test_depot.py` : scan des fichiers suivis, scanner lui-même validé par des cas positifs. Historique : auteur des commits en adresse `noreply` | Vert |
| CI sur runner | Workflow `tests` (exécutions 43642889490 et 43642953438) | Vert |

## Essai réel (workflow, journal, résultat constaté)
Workflow `smoke`, exécution 43643023661, case « tester_claude » cochée. Constaté dans le journal :
- **État sur `data`** : branche créée, écriture puis relecture identiques. Contenu constaté : `state/smoke.json`, `state/claude.json`, `sante/2026-11.jsonl`.
- **Gemini** : 12 modèles découverts et classés. Les trois plus récents ont répondu 503 « high demand », le quatrième (`gemini-3.6-flash`) a répondu : le repli entre modèles, qui manquait aux anciens scripts, a servi en conditions réelles.
- **Claude** : clé valide (`GET /v1/models` : 200) ; appel minimal accepté ; 23 tokens en entrée, 4 en sortie, 0,000086 $ ; compteur du mois écrit sur `data`.
- **Telegram** : **échec**, `HTTP 400 Bad Request: chat not found` dès le premier message. Le jeton du bot est accepté (pas de 401) ; c'est l'identifiant de discussion qui n'est pas reconnu. Le code a réagi comme prévu (erreur claire, aucun secret dans le journal).
- Aucun secret n'apparaît dans le journal du workflow.

## Non vérifié
- **Réception sur Telegram** et découpage réel d'un long message (A6 est vérifié par tests, pas encore côté Telegram) : bloqué par « chat not found ».
- **Mode JSON de Gemini** (`responseMimeType`) avec un vrai appel : le `smoke` n'utilise pas le mode JSON. Il sera exercé en V2.
- **Relais Claude lors d'une vraie panne Gemini** : vérifié par simulation uniquement.
- Alerte santé à 80 % du plafond : lot V5.

## Écarts à la spec
- Un type de message `🧪 Test` s'ajoute aux six en-têtes du § 8.1, utilisé uniquement par `smoke`.
- Le plafond `CLAUDE_PLAFOND_USD_MOIS` se lit comme une *variable* du dépôt (facultative), pas comme un secret ; défaut 5 $ dans `config/parametres.yaml`.
- Aucune correction de la spec nécessaire.

## Choix faits sans le porteur
- Modèle de secours : `claude-sonnet-5-5` (2 $ / 10 $ par million de tokens), paramétrable dans `config/parametres.yaml`.
- Refus préventif si dépense du mois + borne haute de l'appel dépasserait le plafond (plus strict que « plafond atteint »).
- Fuseau en décalage fixe UTC+1 ; clones Git superficiels pour l'état ; commits du bot sous une adresse `noreply`.
- Numérotation « (n/N) » dans l'en-tête des messages découpés.
- `smoke` a envoyé la requête Claude minimale (0,000086 $) pour valider la forme de l'appel.

## À regarder sur le téléphone (cinq points au plus)
Après correction de l'identifiant de discussion et un nouvel essai `smoke` :
1. Un message « 🧪 Test » court est arrivé.
2. Un second message « 🧪 Test (1/N) » à « (N/N) » est arrivé en plusieurs parties, dans l'ordre.
3. Dans ce message, les titres sont en gras et les liens « Lien de l'article … » sont cliquables, suivis de « (FR) ».
4. Aucune balise brute (`<b>`, `<a …>`) n'est visible dans le texte.

## Suite
Arrêt sur Telegram (une question au porteur). Une fois l'essai Telegram vert : V0 est clos et V1 (collecte et alertes) commence.
