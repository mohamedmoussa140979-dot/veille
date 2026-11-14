# Inventaire — V1 collecte et alertes — 14/11/2026

Pages et flux relevés depuis le poste du porteur (une requête par page, en-têtes de navigateur). Les mêmes accès restent à confirmer depuis un runner GitHub (essai réel de V1).

## Ce que V1 reprend des anciens scripts

| Ancien code | Ce qu'on en garde | Ce qu'on change |
|---|---|---|
| `sitemoussam/monitor.py` · `SITES` (44 sources) | La liste, avec les corrections de la spec § 6.1 | Passage en `config/sources.yaml` ; Macsa et Tunisie Valeurs retirés |
| `monitor.py` · `get_articles` (lecteur générique : liens du même domaine, titre ≥ 30 caractères, 12 pour CMF) | Principe du lecteur `html-generique` ; lecteurs CMF et BVMT (pages qui fonctionnent) | Dates et résumés quand la page les donne ; tests sur pages enregistrées |
| `monitor.py` · filtre (`SPORT`, `GUERRE`, `ARTS`, `EXCEPTIONS`, `URL_EXCLUS`, sites exemptés) | Les listes de mots, les expressions conservées (« guerre commerciale », « club de Paris »…), les segments d'URL exclus, l'exemption des régulateurs et agences | Déplacé dans `config/exclusions.yaml` ; exemption portée par un champ `filtre` de la source (voir « Écarts ») |
| `monitor.py` · alertes ntfy | — | Abandonné (V11) : Telegram 🔔 |
| `brief.py` · flux RSS | Liste des flux | Lecture par `feedparser` ; WMC et Tunisie Numérique passent en HTML (constat ci-dessous) |
| `veille_awb.py` · `resoudre_lien`, `lien_traduit` | Forme `translate.goog` (hôte avec tirets doublés, `_x_tr_sl/_x_tr_tl/_x_tr_hl`), liste de domaines sans traduction | La résolution hors ligne des liens Google News ne marche plus (ci-dessous) |

## Hypothèses de la spec vérifiées

| # | Hypothèse | Constat | Suite |
|---|---|---|---|
| I1 | BCT : bloc d'actualités lisible sur `index.jsp` ; `page.jsp?id=226` (circulaires) | HTTP 200 sur les deux (109 Ko et 156 Ko). Flux `flux_rss.jsp?val=actualites` : connexion fermée par le serveur (maintenance, comme la spec l'annonce) | Lecteur `bct` sur ces deux pages ; flux surveillé, jamais requis |
| I2 | INS : `/communique-de-presse` lisible | HTTP 200 (1,0 Mo) | Lecteur `ins` |
| I3 | CMF et BVMT lisibles | HTTP 200 sur l'accueil CMF, la page « avis et décisions » CMF, « avis-decisions » et « publications-societes » BVMT | Lecteurs `cmf` et `bvmt` |
| I4 | Flux WMC et Tunisie Numérique « rejetés par un lecteur XML trop strict » | **Faux** : les deux renvoient la page d'accueil HTML (0 `<item>`). WMC n'annonce aucun flux ; Tunisie Numérique annonce `/feed/` mais sert du HTML | Spec corrigée (§ 6.1) : `html-generique` sur la page d'accueil |
| I5 | France24 « plante sur l'accent de l'URL » | L'accent n'est plus le problème : la rubrique `/fr/économie/rss` a été renommée, l'ancienne adresse boucle en redirections (> 30). Le flux actuel est `/fr/%C3%A9co-tech/rss` (30 articles, XML valide) | Spec corrigée (§ 6.1) |
| I6 | Flux RSS Le Monde Économie, TechCabal, Business News | HTTP 200, XML | Repris tels quels |
| I7 | Liens Google News « résolus » par la logique de `resoudre_lien` | **Partiellement faux** : les liens actuels (`news.google.com/rss/articles/CBMi…`) se décodent en un jeton opaque (`AU_yqL…`), pas en URL ; l'ancien décodage hors ligne ne rend plus rien. La page d'article fournit une signature et un horodatage, qui servent à un appel de résolution non documenté de Google | **Question posée au porteur** (voir bilan et `ETAT.md`) |

## Sondes refusées par le contrôle d'autorisation

Deux sondes ont été refusées automatiquement et **non rejouées** : essayer plusieurs en-têtes `User-Agent` sur les flux qui renvoient du HTML (équivalent d'un contournement de blocage) ; appeler le point d'accès non documenté `batchexecute` de Google News pour résoudre un lien. La première n'est pas nécessaire (repli HTML). La seconde conditionne le critère A12.

## Décisions d'implémentation prévues (sans effet sur V1–V42)

- Lecteurs sous `veille/lecteurs/` : un module par type de source ; un article = `id` (hachage de l'URL normalisée), `source`, `titre`, `url`, `url_traduite`, `publie_le`, `langue`, `payant`, `resume`.
- Champ optionnel `filtre` (booléen, `true` par défaut) dans `sources.yaml` : `false` exempte la source du filtre éditorial (régulateurs, agences de notation, institutions), comme `SITES_EXEMPTES` dans l'ancien script. Ajout à la spec § 6.2.
- `ilboursa` et `Tustex` restent des sources d'**articles** de presse (liste validée, V28). L'interdit V42 porte sur les **données de Bourse** (cours, indices) ; à confirmer par le porteur, désactivable en une ligne (`actif: false`).
