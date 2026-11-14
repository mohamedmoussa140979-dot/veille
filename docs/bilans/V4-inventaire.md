# Inventaire — V4 AWB — 15/11/2026

## Ce que V4 reprend de `veille_awb.py`
| Ancien code | Ce qu'on en garde | Ce qu'on change |
|---|---|---|
| `SUJETS` (AWB, TN, SOUV français-anglais, SOUV arabe, TECH), motifs, poids de requêtes, seuils, fenêtres | Intégralement, dans `config/awb.yaml` (48 requêtes Google News, 8 requêtes GDELT, Finextra), converti par script depuis l'ancien fichier sans le modifier | Modifiable sans toucher au code |
| Filtres (bruit, publicité, sources exclues), bonus de sources de qualité, 21 signaux de score | Identiques | — |
| Regroupement par événement (acteur × pays, 72 h), un message par événement | Identique | État `state/awb_vus.json` sur la branche `data` (au lieu de `seen.json` commité) |
| `traduire` : gtx → clients5 → MyMemory, texte d'origine en dernier recours | Même ordre, mêmes plafonds | Passage par le client HTTP commun (essais, journal) ; **bogue corrigé** : la réponse « clients5 » de forme `[["texte", "en"]]` donnait la première lettre seulement ; compteurs de réussite pour le contrôle de santé dédié (V5) |
| `resoudre_link` / `lien_traduit` | Forme `translate.goog` | Résolution Google News par la méthode de V1 (cache partagé) ; un lien non résolu écarte l'article ; sujet TECH passe toujours par GDELT et Finextra (liens réels) |
| Un message Telegram par article (jusqu'à 30) | Même contenu par article | **Un seul message 🏦 groupé** par passage (sections par sujet), découpé si besoin (spec § 8.1) |

## Hypothèses vérifiées
| # | Hypothèse | Constat |
|---|---|---|
| A1 | Google News répond pour les requêtes AWB | Oui (requête « Attijariwafa bank », locale MA : HTTP 200, 9 entrées) |
| A2 | GDELT répond sans clé | **Limité** : « une requête toutes les 5 secondes » (HTTP 429 sinon). Le client GDELT espace donc ses appels de 5,2 s (8 requêtes ≈ 42 s) |
| A3 | Finextra lisible depuis un runner GitHub | **Non** (HTTP 403, constat de V1). Le sujet TECH repose alors sur GDELT seul ; l'anomalie est journalisée |
| A4 | Services de traduction gratuits | MyMemory répond mais traduit mal le vocabulaire bancaire (« central bank » → « institut d'émission ») ; `gtx` répond 429 depuis le poste du porteur (à vérifier sur un runner). Quand tout échoue, le titre d'origine et le lien « Lire en français » restent |
| A5 | Charge raisonnable | ~140 requêtes Google News par passage (espacées de 0,4 s) : une à deux minutes ; deux passages par jour |

## Décisions d'implémentation (sans effet sur V1–V42)
- Aucun message quand rien ne dépasse les seuils (comme l'ancien script).
- Les articles d'un message qui n'a pas pu partir (Telegram en panne) ne sont pas marqués envoyés ; ils sont seulement mémorisés comme vus au sens « déjà évalué ».
- Les compteurs de traduction (`state/awb.json`) et l'événement `awb_traduction_sans_donnee` alimenteront le contrôle de santé du lot V5.
