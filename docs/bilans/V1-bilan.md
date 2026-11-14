# Bilan — V1 collecte et alertes — 14/11/2026

## En une phrase
La collecte de 49 sources (régulateurs, agences, presse, flux internationaux) tourne sur GitHub, mémorise ce qu'elle a vu, résout les liens Google News, produit des liens traduits et sait envoyer des alertes 🔔 avec plage silencieuse ; la seule vraie alerte à constater sera la première publication BCT ou CMF après la mise en route.

## Fait
- **Lecteurs** (`veille/collecte/lecteurs/`) : `rss`, `html-generique`, `bct` (actualités et circulaires), `ins`, `cmf` (deux formats de pages), `bvmt` (avis et publications), `google-news`. Une page lisible sans aucun article est une **erreur**, jamais un « zéro nouveauté ».
- **Liens** : paramètres de suivi retirés, résolution des liens Google News (cache 60 jours), `url_traduite` (forme `translate.goog`) pour l'anglais et l'arabe non payants, détection de l'arabe dans le titre.
- **Filtre éditorial** : listes de l'ancien script déplacées dans `config/exclusions.yaml` (sport, guerre, arts, plus faits divers, catastrophes, people), appliquées au titre et au résumé ; régulateurs, agences et institutions exemptés (`filtre: false`).
- **Déduplication** : par URL normalisée, puis par titre proche (champ `groupe`).
- **Alertes** : sources `alerte: true` (BCT ×2, CMF ×3, Moody's, S&P, Fitch), un seul message par fait, plage silencieuse 22:00–07:00 (envoi groupé au premier passage après 07:00), alertes conservées si Telegram est en panne.
- **État sur `data`** : `vus` (60 jours), articles du jour, titres récents, cache des liens, état par source (pour le contrôle de santé de V5), alertes en attente ; purge des articles au-delà de 90 jours.
- **Premier passage d'une source** : tout est mémorisé sans alerte, seuls les articles de moins de 24 h sont conservés (pas de rafale d'alertes au démarrage ni après une panne initiale).
- **Workflow `collecte`** : crons de la spec § 5 (en UTC, minutes décalées), case « essai_alerte ».
- `config/sources.yaml` : 49 sources ; `python -m veille.collecte --a-blanc` pour un essai local sans Git ni Telegram.

## Vérifié, et comment
| Critère | Commande ou contrôle | Résultat |
|---|---|---|
| A1 — `pytest` vert, lecteurs BCT, INS, CMF, BVMT, RSS sur pages enregistrées | `pytest` : 151 tests, lecteurs testés sur des pages réelles réduites et anonymisées (adresses de contact des éditeurs retirées) ; `ruff` vert ; CI GitHub verte | Vert |
| A2 — une collecte réelle ramène au moins un article de chaque source, ou l'anomalie apparaît au rapport de santé | Workflow `collecte` (exécution 43650043158) sur un runner GitHub : **48 sources sur 49 lues**, 1 886 articles. Finextra : HTTP 403 depuis les serveurs GitHub (il répond depuis un poste personnel) : anomalie journalisée sur `data` (`sante/2026-11.jsonl`), source non contournée | Vert avec une anomalie signalée |
| A3 — alerte BCT/CMF au passage suivant ; dans la plage silencieuse, à 07:00 | Tests de bout en bout sur pages réelles : alerte immédiate, alerte de nuit différée puis envoyée au premier passage après 07:00, Telegram en panne puis repris. **Pas de vraie publication BCT/CMF attendue pendant l'essai** : l'alerte réelle n'est pas encore constatée ; deux alertes d'exemple envoyées pour juger le rendu (voir ci-dessous) | Vert par tests ; réel à constater |
| A12 — lien traduit sur trois hôtes réels : anglais, arabe, Google News résolu | Ouverture des `url_traduite` : **TechCabal** (anglais) HTTP 200 ; **cmf.tn** (arabe) HTTP 200 ; **apanews.net** (article Fitch obtenu via Google News résolu) HTTP 200, titre traduit | Vert |
| Liens (préparation de A4) | Sur les 97 articles écrits sur `data` par le runner : 0 lien Google News, 0 paramètre `utm_`/`fbclid` | Vert |
| Rien sur `main` | `git ls-tree origin/main` : aucun `state/`, `articles/`, `sante/` | Vert |

## Essai réel (workflow, journal, résultat constaté)
- Exécution 43650043158 : 48/49 sources, 56 liens Google News résolus (0 échec), 97 nouveaux articles (premier passage, 24 h), 65 rejetés par le filtre (sport 25, arts 12, guerre 14, rubriques d'URL 15…), 0 alerte (normal au premier passage).
- Essai d'alerte (exécution 43650375486) : deux messages d'exemple, voir « À regarder sur le téléphone ».
- Essai local (poste du porteur) avant fusion : 49/49 sources lues ; second passage : 0 nouveauté.

## Non vérifié
- **Alerte réelle BCT/CMF** : dépend d'une publication ; à constater dans les jours qui viennent.
- **Rendu sur téléphone** (alertes, liens cliquables, lien « FR ») : voir ci-dessous.
- **Lien traduit pour Reuters et MarketWatch** : `translate.goog` répond HTTP 400 depuis un script ; je ne sais pas si un navigateur obtiendrait mieux. Par prudence ces deux hôtes n'ont pas de lien « FR ».
- **Titre en français** (A12, « titre affiché en français, titre d'origine conservé ») : la collecte conserve `titre_origine` ; la traduction du titre est rédigée par l'IA à l'édition (lot V2).
- **Durée réelle d'un passage** et consommation GitHub : à lire sur les premières exécutions planifiées.

## Écarts à la spec
- § 6.1 corrigé : flux WMC et Tunisie Numérique = pages HTML (passés en `html-generique`) ; France24 = nouvelle adresse du flux. Spec modifiée dans le commit de l'inventaire.
- § 6.2 : champ facultatif `filtre` ajouté (exemption du filtre éditorial).
- § 6.3 : la résolution hors ligne des liens Google News ne fonctionne plus ; méthode retenue avec votre accord (appel Google non documenté, repli : article écarté). Liens traduits : Reuters et MarketWatch exclus (HTTP 400). Spec modifiée.
- CMF : l'ancien « 61 à 124 articles par page » comptait des liens de menu ; les vraies listes font 20 à 30 éléments par page. Pas d'impact sur la spec.

## Choix faits sans le porteur
- **Alertes** : BCT (2 pages), CMF avis et visas (3 pages) et les trois agences de notation. Pas d'alerte pour INS, BVMT, ni les communiqués et états financiers CMF (trop nombreux). Modifiable dans `sources.yaml` (`alerte`).
- **`ilboursa` et Tustex** conservés comme sources d'**articles** (liste validée V28 ; l'interdit V42 vise les données de Bourse). À confirmer ; `actif: false` pour les retirer.
- **WSJ remplacé par MarketWatch** (flux « top stories »). Ses articles sont souvent de la finance personnelle américaine : le classement de l'IA (V2) devra les écarter. À changer si vous préférez un autre flux marchés.
- **Finextra** laissé actif malgré le 403 des serveurs GitHub, pour que l'anomalie remonte au contrôle de santé (V5). Même blocage attendu pour la veille AWB (V4).
- **R&I** (agence japonaise citée au § 4 de la spec) : aucune source dans les anciens scripts, pas ajoutée.
- **Presse tunisienne en RSS** quand le site en publie un (Business News, Économiste Maghrébin, Kapitalis, La Presse, African Manager), plutôt qu'en lecture HTML.
- Fenêtres : article ignoré au-delà de 14 jours ; alerte seulement si la publication a moins de 7 jours ; au plus 80 résolutions de liens par passage.
- Mots exclus étendus (faits divers, catastrophes, people, quelques mots anglais). La **politique** n'est pas filtrée par mots : c'est le classement de l'IA qui tranche le cas limite (V2).

## À regarder sur le téléphone (cinq points au plus)
1. Deux messages « 🔔 Alerte » d'exemple viennent d'arriver : le premier liste « BCT (essai) » et « Fitch (essai) », le second est précédé de « Détectées pendant la plage silencieuse (22:00–07:00) ».
2. Dans l'alerte Fitch : le tag « [EN] », le lien du titre et un lien « FR » cliquables.
3. Le lien « FR » ouvre bien la page traduite en français (page apanews.net).
4. Les titres sont lisibles, sans balise brute.
5. Dans les jours qui suivent : une vraie alerte BCT ou CMF arrive, et rien en pleine nuit (22:00–07:00).

## Suite
V2 (synthèses) : classement et rédaction par l'IA, fichier d'édition, Telegram 🌅/🌆, archive Pages, workflows du matin, du soir et du week-end.
