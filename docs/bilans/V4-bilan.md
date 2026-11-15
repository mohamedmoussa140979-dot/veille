# Bilan — V4 AWB — 15/11/2026

## En une phrase
La veille AWB (Attijariwafa bank, secteur bancaire tunisien, risque souverain, cas d'usage technologiques) tourne sur le socle, deux fois par jour, avec un message 🏦 groupé, des titres traduits en français et des liens traduits ; le sujet technologique reste fragile car GDELT et Finextra limitent ou bloquent les serveurs GitHub.

## Fait
- **Configuration reprise** de `veille_awb.py` dans `config/awb.yaml` (conversion par script, sans toucher à l'ancien dépôt) : 5 blocs de sujets, 48 requêtes Google News (français, arabe, anglais), 8 requêtes GDELT, Finextra, filtres de bruit, de publicité et de sources, bonus de sources de qualité, 21 signaux de score, regroupement par événement (acteur × pays, 72 h).
- **Collecte** via le client HTTP commun, avec trois clients distincts (Google News espacé de 0,4 s, GDELT espacé de 8 s, autres flux) ; une panne de flux n'arrête jamais la collecte.
- **Traduction** : Google « gtx », puis « clients5 », puis MyMemory, sinon texte d'origine ; titres et résumés traduits, titre d'origine conservé en italique, lien « Lire en français » (`translate.goog`). **Bogue de l'ancien code corrigé** : la réponse « clients5 » de forme `[["texte", "en"]]` n'en donnait que la première lettre.
- **Liens** : Google News résolu par la méthode de V1 (cache partagé) ; un lien non résolu écarte l'article ; paramètres de suivi retirés.
- **Un seul message 🏦 groupé** par passage, une section par sujet, tri par score (🔴 ≥ 24, 🟠 ≥ 19, ⚪️ sinon) ; rien n'est envoyé quand rien ne dépasse les seuils.
- **Mémoire** sur `data` (`state/awb_vus.json`, 8 000 entrées au plus), compteurs de traduction (`state/awb.json`) pour le contrôle de santé.
- **Workflow `awb`** : tous les jours à 08:30 et 18:30 (heure de Tunis).

## Vérifié, et comment
| Contrôle | Méthode | Résultat |
|---|---|---|
| Reprise fidèle de la logique | 30 tests : filtres, score, bonus, événements, sélection (doublons, fenêtre de 72 h, seuils, tri), traduction (repli, abandon de gtx après 3 échecs, plafond de 450 caractères, 6 formes de réponse « clients5 »), message (échappement, sections), passage complet (Telegram en panne, liens Google News, santé) | Vert |
| Passage réel sur un runner GitHub | Exécution 43655755217 : 123 articles pertinents, 38 nouveaux, 12 envoyés, message 🏦 conforme (titres arabes et anglais rendus en français, lien « Lire en français » et « Source ») | Vert |
| Mémoire | Les 38 nouveaux sont mémorisés ; un second passage ne renvoie pas les mêmes articles (test) | Vert |

## Essai réel (workflow, journal, résultat constaté)
- Durée : environ 7 minutes (≈ 140 requêtes Google News, 8 requêtes GDELT, résolution des liens, traductions).
- **GDELT : HTTP 429 sur 6 requêtes sur 8** malgré un espacement de 5,2 s (limite annoncée : une requête toutes les 5 s) ; corrigé par un espacement de 8 s, à constater au prochain passage.
- **Finextra : HTTP 403** depuis les serveurs GitHub (constat déjà fait en V1, source non contournée).
- **`gtx` : HTTP 429** depuis le runner : les repli « clients5 » puis MyMemory ont pris le relais ; les titres du message sont en français.
- Les six avertissements GDELT et celui de Finextra sont journalisés sur `data` (`sante/`), et seront repris par le contrôle de santé.

## Non vérifié
- **Le sujet 🟪 TECH** : il repose uniquement sur GDELT et Finextra ; si GDELT continue à répondre 429 et Finextra 403, ce sujet restera vide depuis GitHub. À juger après quelques passages (le contrôle de santé le signale).
- **Qualité de la traduction de secours** : MyMemory traduit mal le vocabulaire bancaire (constaté sur « central bank »). Les titres de l'essai étaient corrects.
- **Rendu sur le téléphone** du message 🏦 (longueur, sections, liens).
- Le **secret `MYMEMORY_MAIL`** n'est pas posé (facultatif, spec § 11) : quota gratuit de MyMemory plus bas.

## Écarts à la spec
- Un message **groupé** par passage (« message 🏦 deux fois par jour »), alors que l'ancien script envoyait un message par article.
- Aucun autre écart.

## Choix faits sans le porteur
- Aucun message quand rien de nouveau n'atteint les seuils (comme l'ancien script).
- Seuils, poids et listes inchangés par rapport à l'ancien script (modifiables dans `config/awb.yaml`).
- Au plus 30 articles par message (comme l'ancien script).
- Les articles d'un message qui n'a pas pu partir ne sont pas marqués envoyés (ils seront évalués à nouveau).

## À regarder sur le téléphone (cinq points au plus)
1. Le message « 🏦 AWB » de 00:03 : une section « 🟦 AWB », des titres en français, une ligne d'origine en italique, la source et l'heure.
2. Les deux liens de chaque article : « 🇫🇷 Lire en français » ouvre la page traduite, « 🔗 Source » l'article.
3. Le message n'est pas trop long ni répétitif ; signaler les articles sans intérêt (sujet, source).
4. Lundi : un message 🏦 vers 08:30 et un vers 18:30, seulement s'il y a du nouveau.
5. Absence ou présence d'articles « 🟪 TECH » dans les prochains messages.

## Suite
V5 (santé et bascule).
