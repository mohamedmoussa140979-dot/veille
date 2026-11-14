# Inventaire — V2 synthèses — 14/11/2026

## Ce que V2 reprend ou réutilise
| Origine | Ce qu'on en garde | Ce qu'on change |
|---|---|---|
| `digest.py` (consigne de synthèse) | Rôle (analyste), ligne éditoriale, regroupement des doublons, « L'essentiel » de 3 à 5 lignes | Six chapitres de la spec § 4, sortie en JSON validé (et non en HTML libre), liens vers tous les articles d'un sujet |
| V0 : `ia.Ia.generer_json` | Gemini puis Claude en secours, JSON validé contre un schéma, un nouvel essai | — |
| V0 : `telegram.envoyer` | Découpage, repli texte brut, en-têtes 🌅 🌆 | — |
| V1 : articles du jour sur `data` | Source des éditions | Ajout de `vu_le` (première observation) : une publication datée du seul jour (00:00) ne serait sinon jamais dans l'édition du soir |

## Hypothèses vérifiées à l'inventaire
| # | Hypothèse | Constat |
|---|---|---|
| J1 | GitHub Pages en source « GitHub Actions » est actif | Confirmé par l'API : `build_type: workflow`, adresse `https://mohamedmoussa140979-dot.github.io/veille/` |
| J2 | Le mode JSON de Gemini (`responseMimeType`) répond avec un JSON valide sur un vrai prompt d'édition | **À vérifier à l'essai réel** (non testé en V0) |
| J3 | Un classement de 100 à 300 titres tient dans un seul appel | Les 97 articles du premier passage font environ 6 000 tokens en entrée compacte : oui |
| J4 | Le déploiement Pages par `actions/deploy-pages` fonctionne depuis un workflow planifié | **À vérifier à l'essai réel** |

## Décisions d'implémentation (sans effet sur V1–V42)
- **Deux appels IA au plus** par édition : (1) classement et regroupement, (2) rédaction. Un JSON invalide donne un seul nouvel essai (déjà dans `Ia.generer_json`).
- L'IA ne manipule que des **identifiants d'articles** ; le code reconstruit les liens, titres, sources et dates à partir des données collectées, et **rejette tout identifiant inconnu** (un sujet sans article valide disparaît). Aucun lien n'est jamais écrit par l'IA.
- Fenêtres : édition du matin = depuis la dernière édition du soir (jours ouvrés : depuis 18:30 la veille ; lundi : depuis vendredi 18:30) ; soir = depuis 07:30 ; week-end = 24 h. Critère : `vu_le`.
- L'édition du week-end s'enregistre comme `matin` (le contrat ne connaît que `matin` et `soir`) ; son message Telegram porte l'en-tête 🌅.
- Les quatre chiffres et les tableaux des chapitres 3 et 4 restent à `null` jusqu'à V3.
- Archive : une page par édition, une page par mois, un index de recherche des 30 derniers jours ; construite à chaque édition à partir de **toutes** les éditions de la branche `data`.
- Le titre en français des articles non francophones est rédigé par l'IA à l'édition ; `titre_origine` conserve l'original.
