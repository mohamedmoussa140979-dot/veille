# Bilan — V2 synthèses — 15/11/2026

## En une phrase
Les éditions du matin, du soir et du week-end sont produites par l'IA, validées contre le contrat `schema/edition.v1.json`, écrites sur `data`, envoyées sur Telegram (🌅/🌆) et publiées dans une archive GitHub Pages ; un premier essai réel a produit 22 sujets à partir de 96 articles.

## Fait
- **Contrat** `schema/edition.v1.json` (spec § 8.2) et validation en deux niveaux : schéma, puis règles du § 4 (articles cités présents, aucun lien Google News, aucun `utm_`, chapitres dans l'ordre).
- **Fenêtre d'édition** : du dernier passage d'édition à maintenant (plafond 72 h) ; week-end : 24 h. Critère : première observation (`vu_le`, ajouté aux articles de V1), pas la date de publication, pour ne pas perdre les publications datées du seul jour.
- **Deux appels IA par édition** (Gemini, Claude en secours, plafond) : classement et regroupement, puis rédaction. L'IA ne manipule que des **identifiants** : le code reconstruit liens, titres, sources, dates, et **rejette tout identifiant inconnu**. Au plus 5 sujets par chapitre ; un chapitre vide n'apparaît pas ; l'essentiel est toujours présent (repli sur les premiers sujets si l'IA n'en donne pas).
- **Titres en français** pour les articles non francophones, `titre_origine` conservé.
- **Telegram** : l'essentiel, puis les chapitres avec leurs liens (« (FR) » après le lien d'un article étranger, 🔒 pour une source payante, 🏠 pour l'impact ménage), puis le lien « Édition complète ».
- **Archive** (`veille/edition/archive.py`) : une page par édition, un index par mois, un index général, recherche sur 30 jours côté navigateur ; tout texte échappé, aucune image, aucun script externe. Publiée **une fois par édition** par les actions officielles Pages.
- **Workflow `edition`** : crons de la spec § 5 (matin 07:30, soir 18:30, week-end 09:30, heure de Tunis), type d'édition lu dans l'horaire du workflow (fiable même si GitHub retarde l'exécution), case de relance avec fenêtre forcée.
- Si l'IA est indisponible ou le plafond Claude atteint : **aucune édition**, message ⚠️ Santé « Synthèse … non générée : raison », événement dans `sante/`.
- Quatre chiffres de l'en-tête et tableaux des chapitres 3 et 4 : `null` jusqu'à V3, comme prévu.

## Vérifié, et comment
| Critère | Commande ou contrôle | Résultat |
|---|---|---|
| A4 — chapitres non vides dans l'ordre, chaque sujet avec au moins un lien d'origine, aucun lien Google News, aucun `utm_` | Tests (`test_edition.py`) sur une IA simulée qui invente des identifiants ; **sur l'édition réelle** : validation du contrat passée avant écriture, page publiée relue : aucun `news.google.com`, aucune image, aucun script externe | Vert |
| A5 — fichier conforme au schéma v1, donnée absente = `null` | 9 mutations invalides refusées par les tests ; l'édition réelle valide le schéma ; `chiffres` à `null` (jamais 0) | Vert |
| Contenu | Lecture de l'édition réelle : textes factuels, reformulés, impact ménage présent sur Économie tunisienne, titres français pour les 4 articles anglais | Correct (voir « Choix ») |
| CI | 205 tests, `ruff` ; CI GitHub verte sur chaque branche | Vert |

## Essai réel (workflow, journal, résultat constaté)
- Exécution 43652400351 : **échec** — Gemini a renvoyé la liste classée comme un tableau JSON nu au lieu de l'objet `{"articles": …}` ; la forme était la seule fautive. Corrigé : normalisation tolérante, exemple de format dans les prompts, messages d'erreur de schéma courts (le message natif recopiait toute la donnée dans le journal et dans la demande de reprise).
- Exécution 43653118998 : **succès** (édition + Pages). Édition `2026-11-15-matin` (week-end) : fenêtre 24 h, 96 articles, **22 sujets, 30 articles cités**, modèle `gemini-3.5-flash`. Avant lui, trois modèles plus récents ont répondu 503, 429 ou dépassé 180 s : le repli entre modèles a servi en conditions réelles.
- Archive en ligne : `https://mohamedmoussa140979-dot.github.io/veille/` (accueil, `2026-11/`, page d'édition, `recherche.json` : HTTP 200).
- Message Telegram : envoyé (statut « envoyé » du journal).

## Non vérifié
- **Rendu sur le téléphone** du message 🌅 et de la page d'archive (voir ci-dessous).
- **Premier passage planifié** : l'horaire réel (dimanche 09:30 pour le week-end, lundi 07:30) et le type d'édition déduit du cron restent à constater.
- **Le relais Claude lors d'une vraie panne Gemini** : simulé seulement. Le plafond de 5 $ n'a pas été touché (compteur : 0,000086 $).
- **Durée** : l'édition d'essai a pris environ 8 minutes à cause des délais dépassés de Gemini (180 s par essai) ; à surveiller sur les exécutions planifiées.
- Le dépôt des éditions sur Mizeniti est la phase 2 (non démarrée).

## Écarts à la spec
- Le contrat ne connaît que `matin` et `soir` : l'édition du week-end s'enregistre comme `matin` (message 🌅).
- Aucune autre correction de la spec.

## Choix faits sans le porteur
- **MarketWatch** : le flux « top stories » apportait de la finance personnelle américaine ; remplacé par « Market Pulse » (titres macro et marchés) et règle de prompt qui écarte la finance personnelle. À réévaluer à la lecture de quelques éditions.
- **La politique n'est pas filtrée par mots** : le classement de l'IA tranche. Dans l'essai, un sujet « Nvidia » (affaire politique et diplomatique américaine) est passé en Technologie : cas limite à surveiller.
- Le message Telegram n'est pas silencieux (les éditions sont attendues) ; seuls les essais le seraient.
- Quand l'IA ne rédige pas un sujet, repli sur le titre et le résumé de l'article plutôt qu'un trou.

## À regarder sur le téléphone (cinq points au plus)
1. Le message « 🌅 Synthèse matin » reçu vers 00:25 : l'essentiel en tête, puis les chapitres, un lien « Édition complète » en dernière ligne.
2. Les liens des sources s'ouvrent ; le « (FR) » d'un article anglais ouvre la page traduite ; 🔒 sur une source payante.
3. La page `https://mohamedmoussa140979-dot.github.io/veille/` : lisible sur iPhone, recherche (à partir de 3 lettres) et page du mois.
4. Le texte de l'édition est-il juste et utile ? Signaler un sujet qui n'a pas sa place (par exemple finance personnelle américaine, politique américaine).
5. Dimanche 09:30 (Tunis) : l'édition du week-end arrive d'elle-même.

## Suite
V3 (marchés) : Bourse de Tunis via le Worker `marche-lecture` de Mizeniti, BCT (taux et cours), Yahoo (international), deux points 📈, tableaux des chapitres 3 et 4 et quatre chiffres de l'édition.
