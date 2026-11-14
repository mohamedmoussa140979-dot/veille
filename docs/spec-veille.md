# Spec — Veille économique consolidée (dépôt `veille`)

Version du 14/11/2026. Validée par le porteur au fil du cadrage du 14/11 (journal : `journal-decisions.md`, décisions V1 à V42).

## 1. But

Remplacer les quatre dépôts actuels (`sitemoussam`, `veille-bfi`, `veille-awb`, `veille-tunisie`) par **un seul dépôt public** `mohamedmoussa140979-dot/veille`, qui :

1. collecte l'actualité économique (Tunisie, Afrique, international, technologie) ;
2. envoie des **alertes immédiates** sur Telegram pour les régulateurs et les agences de notation ;
3. produit **deux synthèses par jour** organisées en chapitres, publiées sur Telegram, dans une archive HTML (GitHub Pages) et, en phase 2, dans l'écran Actualités de Mizeniti ;
4. publie les **points marchés** (clôture de la Bourse de Tunis, clôture internationale ; pas de mi-séance, V42) ;
5. publie la **veille AWB** ;
6. **se surveille lui-même** et prévient quand une source ou une tâche ne produit plus rien.

Le principe du jour et BudgetPilot Alerts sont abandonnés.

## 2. Pourquoi (constats de l'audit du 14/11)

- Panne silencieuse de 35 jours (compte GitHub verrouillé pour facturation, aucune alerte).
- Résumé marchés : toute la partie Bourse de Tunis vide depuis des semaines (irbe7 construit sa page en JavaScript ; le script lisait 0 ligne). **irbe7 est abandonné** (décision V42).
- BCT : 0 article en 34 jours (page 404, flux RSS en maintenance). INS : publications détectées mais sans titre.
- Brief : flux WMC et Tunisie Numérique rejetés (lecteur XML trop strict), France24 plante sur l'accent de l'URL, WSJ vide.
- Gemini : un seul modèle dans le brief, 3 échecs en 9 jours sur une erreur 503.
- Digest : message Telegram coupé au milieu d'une balise HTML, renvoyé en texte brut.
- Code Telegram dupliqué cinq fois, quatre bots, deux sites Pages, `journal.json` (4 Mo) recommité à chaque passage.
- E-mail du porteur et topic ntfy exposés dans des dépôts publics.

## 3. Ligne éditoriale

**Gardé** : économie, finance, réglementation, entreprises et acteurs économiques (cotés ou non), marchés, technologie à fort impact sur les économies, les entreprises ou les ménages.

**Exclu** : sport, arts et culture, guerres et conflits, politique, faits divers, catastrophes naturelles, people, santé grand public.

**Cas limite** : un fait politique ou un conflit à effet économique direct (loi de finances, droits de douane, sanctions, choc pétrolier) est **gardé**, traité sous l'angle économique, et peut figurer dans L'essentiel.

**Mise en œuvre** : deux filtres successifs.
1. Liste de mots exclus (fichier de configuration, modifiable ; en phase 2, depuis le back-office), appliquée au titre et au résumé avant tout appel IA.
2. Classement par l'IA : chaque article reçoit un chapitre ou « hors ligne éditoriale », avec la règle du cas limite dans le prompt.

**Langues** : sources en français, anglais et arabe ; synthèse en **français uniquement**. Un article arabe est lu, résumé en français et cité comme source (pastille « AR »).

## 4. Chapitres de la synthèse

Ordre d'affichage :

| # | Chapitre | Contenu |
|---|---|---|
| 1 | **L'essentiel** | 3 à 5 points, tous chapitres confondus, avec leurs liens. Toujours présent. |
| 2 | **Économie tunisienne** | Quatre rubriques fixes : *Réglementation* (circulaires BCT, JORT, textes fiscaux, réglementation CMF) ; *Notations* (Fitch, Moody's, S&P, R&I : souverain et banques) ; *Statistiques et finances publiques* (INS : croissance, inflation, chômage, commerce extérieur ; indicateurs BCT ; budget, loi de finances) ; *Revue de la presse économique* (y compris actualité bancaire non cotée). Une ligne « Impact ménage » sous les sujets qui s'y prêtent (ex. « TMM +0,25 pt : les crédits à taux variable augmentent »). |
| 3 | **Bourse, entreprises et acteurs économiques** | Communiqués CMF, avis BVMT, publications des sociétés cotées (indicateurs trimestriels, états financiers, AGO et dividendes, augmentations de capital, emprunts obligataires), actualité de tout acteur économique. **Tableau fixe** : TUNINDEX, indice Banques, trois plus fortes hausses et baisses ; chaque ligne mène à sa source (fiche BVMT de la valeur). |
| 4 | **Économie et marchés internationaux** | **Tableau fixe** : Brent, gaz naturel, or, blé ; S&P 500, Euro Stoxx 50, CAC 40, MASI ; EUR/USD ; cours moyens BCT EUR/TND et USD/TND. Puis Fed, BCE, données macro majeures. Chaque ligne mène à sa source. |
| 5 | **Économie africaine** | Maghreb (Maroc, Algérie, Libye), Afrique subsaharienne, institutions (BAD, Afreximbank, FMI Afrique), ZLECAf. |
| 6 | **Technologie** | IA, fintech et paiements, cybersécurité, télécoms, énergie et climat sous l'angle économique, startups tunisiennes. Filtre : impact économique explicite. |

**Règles de forme** : un chapitre vide n'apparaît pas ; 5 sujets au plus par chapitre ; un sujet = titre + 1 à 2 phrases rédigées par l'IA + liens vers **tous** les articles d'origine qui le traitent (un fait couvert par plusieurs sources n'apparaît qu'une fois). Aucun texte d'article reproduit ; aucune image.

## 5. Éditions et tâches

Heures de Tunis (UTC+1, pas d'heure d'été). Les crons GitHub sont en UTC : heure de Tunis − 1. Minutes décalées de l'heure ronde (les exécutions planifiées pile à l'heure sont les plus retardées par GitHub).

| Tâche | Jours | Heures (Tunis) | Sortie |
|---|---|---|---|
| Collecte + alertes immédiates | Lun–ven | 07:15 · 09:15 · 11:15 · 13:15 · 15:15 · 17:15 · 20:15 | 🔔 Telegram |
| Collecte + alertes | Sam–dim | 09:15 · 18:15 | 🔔 Telegram |
| Synthèse du matin | Lun–ven | 07:30 | 🌅 Telegram, archive, fichier d'édition |
| Synthèse du soir | Lun–ven | 18:30 | 🌆 idem |
| Synthèse du week-end | Sam–dim | 09:30 | 🌅 idem |
| Point Bourse de Tunis (séance du jour) | Lun–ven | 17:20, nouvel essai 18:20 si la séance du jour n'est pas encore publiée par Mizeniti | 📈 Telegram |
| Clôture internationale | Lun–ven | 22:45 | 📈 Telegram |
| Veille AWB | Tous les jours | 08:30 · 18:30 | 🏦 Telegram |
| Contrôle de santé | Tous les jours | 21:00 | ⚠️ seulement en cas d'anomalie ; le dimanche, un message « tout va bien » même sans anomalie |

**Édition du matin** : nuit et international, agenda du jour (calendrier INS, échéances connues), articles tunisiens parus depuis l'édition du soir. **Édition du soir** : uniquement ce qui est nouveau depuis le matin. Week-end : une édition couvrant les dernières 24 h.

**Plage silencieuse** des alertes : 22:00–07:00. Une alerte détectée dans la plage part dans un message groupé à 07:00 (au premier passage suivant 07:00).

**Phase 2** : les horaires des collectes et des éditions sont lus dans le back-office de Mizeniti et le déclenchement vient de Mizeniti (`workflow_dispatch`) ; voir `spec-actualites-mizeniti.md` § 6. En phase 1, ils sont dans les fichiers de workflow.

## 6. Sources

### 6.1 Liste
La liste validée est celle des scripts actuels (`monitor.py` : 44 sources ; `brief.py` : 12 flux ; `veille_awb.py` : flux Google News, Finextra, GDELT), avec ces corrections :

| Source | Correction |
|---|---|
| BCT | **Lecteur dédié** sur `https://www.bct.gov.tn/bct/siteprod/index.jsp` : bloc d'actualités (date, titre, lien `actualites.jsp?id=…`), vérifié le 14/11 (dernière actualité du 10/11). Ajouter `page.jsp?id=226` (Circulaires & Notes). Le flux `flux_rss.jsp?val=actualites` est en maintenance le 14/11 : le surveiller, ne pas en dépendre. Retirer `actualites.jsp` (404) et le flux Google News BCT. La même page donne taux directeur, TMM, TRE et cours moyens (tableau du chapitre 4). |
| INS | **Lecteur dédié** sur `https://www.ins.tn/communique-de-presse` : titre, date (`jj-mm-aaaa`), résumé d'une ligne, lien `/publication/…` (vérifié le 14/11). Ajouter `https://www.ins.tn/calendar` pour l'agenda. |
| CMF (7 pages) et BVMT (3 pages) | Fonctionnent (61 à 124 articles par page en 34 jours). Reprendre tels quels. |
| Macsa, Tunisie Valeurs | Retirés (0 article en 34 jours). |
| Flux RSS du brief | Lecture par `feedparser` (tolérant) ; URL encodées ; WSJ (0 article) remplacé par un flux marchés qui répond. **Constats du 14/11 (inventaire V1)** : le flux de Web Manager Center (`/feed/`) et celui de Tunisie Numérique (`/feed/`) renvoient la page d'accueil HTML à un client automatisé, ce n'est pas un problème de lecteur XML : ces deux sites passent en `html-generique` sur leur page d'accueil (comme l'ancien `monitor.py`). France24 : la rubrique a été renommée, l'adresse du flux est `https://www.france24.com/fr/%C3%A9co-tech/rss` (l'ancienne `/fr/économie/rss` boucle en redirections). |
| irbe7 (cours BVMT) | **Abandonné (V42).** Aucun usage, même en repli. Remplacé par le § 6.4. |
| Yahoo Finance (`query1.finance.yahoo.com`) | API non officielle : garder, mais avec contrôle de santé dédié et repli (tiret affiché). |
| Traduction AWB | Services gratuits non officiels (Google « gtx », MyMemory) : garder, contrôle de santé dédié. |

### 6.2 Configuration
Phase 1 : `config/sources.yaml` dans le dépôt. Pour chaque source : `id`, `nom`, `url`, `type` (`rss` | `html-generique` | `bct` | `ins` | `cmf` | `bvmt` | `google-news`), `chapitre` par défaut, `langue`, `alerte` (oui/non), `payant` (oui/non, pastille 🔒), `actif`, et, facultatif, `filtre` (oui par défaut ; `non` exempte la source du filtre éditorial, pour les régulateurs, agences de notation et institutions, comme `SITES_EXEMPTES` dans l'ancien `monitor.py`).

Phase 2 : la même structure est lue depuis l'API du back-office Mizeniti ; le fichier local reste le repli si l'API ne répond pas.

### 6.3 Liens
- Liens Google News **résolus** vers l'URL réelle à la collecte (reprendre la logique de `resoudre_lien` de `veille_awb.py`).
- Paramètres de suivi retirés (`utm_*`, `fbclid`, `gclid`, etc.).
- Déduplication par URL normalisée, puis par titre proche (même fait, plusieurs sources : un sujet, plusieurs liens).
- **Lien traduit** (décision V41) : pour tout article dont la langue n'est pas le français (anglais, arabe), calcul d'une `url_traduite` vers la traduction automatique de Google de la page d'origine (forme `https://<hôte-avec-tirets>.translate.goog/<chemin>?_x_tr_sl=<langue>&_x_tr_tl=fr&_x_tr_hl=fr`, logique existante dans `veille_awb.py`). Pas d'appel d'API, pas de traduction faite par nous, aucun texte reproduit. Pas de lien traduit pour une source marquée `payant`. Si la forme `translate.goog` échoue pour un hôte (test au moment de V1), repli sur `https://translate.google.com/translate?sl=<langue>&tl=fr&u=<url>`.

### 6.4 Données de la Bourse de Tunis (V42)

Ordre des sources, sans autre option :

1. **Données déjà publiées par Mizeniti** (principal). Le Worker `marche-lecture` du dépôt `mizeniti2026-gif/marche-jobs` sert en lecture anonyme `/marche/bourse/index.json` (cours par valeur, date et statut de séance, clôture précédente), `/marche/bourse/indices.json` (TUNINDEX, TUNINDEX20, indices sectoriels), `/marche/bourse/volumes.json`, `/marche/bourse/capitalisation.json` et `/marche/etat.json`. Ces données viennent des fichiers publics de la Bourse (bulletin officiel, `market_resume.ndjson`) et sont publiées par trois passages vers 16:30, 18:00 et 21:40 heure de Tunis. Avantages : mêmes chiffres que l'application, aucune collecte en double, pas de dépendance à l'accès au site de la Bourse depuis les serveurs GitHub. L'adresse du Worker se lit dans `marche-jobs` (README, `EXPO_PUBLIC_MARCHE_URL`) : c'est une hypothèse à confirmer à l'inventaire de V3.
2. **Site de la Bourse directement** (repli, seulement si la route Mizeniti est muette ou périmée) : `https://tunis-stockexchange.com/sites/default/files/historique/data_json/market_resume.ndjson` (mis à jour vers 15:45), puis le bulletin officiel `…/sites/default/files/bulletin/pdf/bullAAAAMMJJ.pdf`. **Risque connu** : en octobre, le site de la Bourse ne répondait ni aux serveurs GitHub ni à Cloudflare (tests du chantier Marché des 24 et 25/10). La chaîne Marché lit aujourd'hui ces fichiers : l'inventaire de V3 vérifie si un runner GitHub du compte machine y accède. S'il n'y accède pas, le repli est retiré et la Bourse s'affiche en tiret quand Mizeniti est muet.

**Exclus** : irbe7, ilboursa, Tustex, Tera Finances, African Markets et tout autre rediffuseur ; le Market Watch de la Bourse (WebSocket à jeton de l'offre commerciale « Market Data ») ; tout navigateur sans tête.

**Conséquences** :
- **Pas de point de mi-séance** : aucune source publique ne donne les cours pendant la séance. Le point 📈 de 11:00 (V17) est supprimé.
- Le point de clôture passe de 14:45 à **17:20**, après le premier passage de publication de Mizeniti. Si la date de séance servie n'est pas celle du jour (jour ouvré) à 17:20, nouvel essai à 18:20, puis message « séance du JJ/MM non encore publiée » ; jour férié sans séance : aucun message.
- Contenu du point Bourse et du tableau du chapitre 3 : TUNINDEX et TUNINDEX20 (valeur, variation du jour, variation annuelle telle que publiée), indice sectoriel Banques s'il figure dans `indices.json`, trois plus fortes hausses et baisses calculées sur `index.json` en ignorant les valeurs non cotées du jour (`v` nul), capitaux échangés si servis. Rien n'est recalculé quand la Bourse le publie.
- Le dépôt `veille` ne modifie jamais `marche-jobs` ni le Worker `marche-lecture` : lecture seule, par HTTP.

## 7. IA

- **Gemini** (clé gratuite, `GEMINI_API_KEY`) : liste de modèles de repli découverte dynamiquement, comme `digest.py` actuel ; nouvel essai sur 429/503 avec attente croissante.
- **Claude** (`ANTHROPIC_API_KEY`) : **secours uniquement**, quand tous les modèles Gemini ont échoué. Plafond mensuel **5 $** (paramètre `CLAUDE_PLAFOND_USD_MOIS`), compteur de consommation tenu dans l'état ; plafond atteint = pas d'appel, synthèse marquée « non générée » et alerte santé.
- Deux appels au plus par édition (classement + rédaction). Sortie de l'IA en **JSON validé** contre un schéma ; JSON invalide = un nouvel essai, puis échec propre.
- Le prompt impose : français, ligne éditoriale du § 3, chapitres du § 4, aucune phrase recopiée d'un article (reformulation), aucune information absente des articles fournis.

## 8. Sorties

### 8.1 Telegram
Un seul bot (`TG_TOKEN_VEILLE`, `TG_CHAT_ID`). En-tête fixe par type : 🔔 Alerte · 🌅 Synthèse matin · 🌆 Synthèse soir · 📈 Marchés · 🏦 AWB · ⚠️ Santé. Synthèse sur Telegram : L'essentiel complet, puis par chapitre titres et liens, puis lien vers l'édition complète sur Pages. Un article non francophone avec `url_traduite` porte, après son lien, un second lien « (FR) ». **Découpage** des messages longs sur des frontières de paragraphe, jamais au milieu d'une balise (limite Telegram 4 096 caractères). Mode HTML avec échappement ; échec HTML = renvoi en texte brut, noté au journal.

### 8.2 Fichier d'édition (contrat avec Mizeniti)
Un fichier JSON par édition, `editions/AAAA-MM-JJ-matin.json` ou `-soir.json`, sur la branche `data`, schéma versionné `schema/edition.v1.json` :

```json
{
  "version": 1,
  "id": "2026-11-17-matin",
  "date": "2026-11-17",
  "edition": "matin",
  "genere_le": "2026-11-17T06:34:12Z",
  "modele": "gemini-…",
  "chiffres": [
    {"cle": "tunindex", "libelle": "TUNINDEX", "valeur": 18989.99, "variation_pct": 0.79, "source_url": "…", "au": "2026-11-14"}
  ],
  "essentiel": [{"texte": "…", "articles": ["a12", "a40"]}],
  "chapitres": [
    {
      "cle": "eco-tunisie",
      "titre": "Économie tunisienne",
      "tableau": null,
      "sujets": [
        {"rubrique": "reglementation", "titre": "…", "texte": "…", "impact_menage": "…", "articles": ["a12"]}
      ]
    }
  ],
  "articles": {
    "a12": {"titre": "…", "source": "BCT", "url": "https://…", "url_traduite": null, "publie_le": "2026-11-16T15:02:00+01:00", "langue": "fr", "payant": false},
    "a40": {"titre": "Titre traduit en français", "titre_origine": "Original English title", "source": "Reuters", "url": "https://…", "url_traduite": "https://…translate.goog/…", "publie_le": "…", "langue": "en", "payant": true}
  }
}
```

Les quatre chiffres de l'en-tête Mizeniti : TUNINDEX, cours BCT EUR/TND, Brent, TMM. Donnée absente : `valeur: null` (jamais 0).

### 8.2 bis Données de Bourse
Voir § 6.4. Chaque chiffre de Bourse porte sa date de séance (`au`) et, si Mizeniti le sert ainsi, la mention « provisoire ». La source affichée est « Bourse de Tunis ».

### 8.3 Archive HTML (GitHub Pages)
Une page par édition générée depuis le fichier JSON, une page d'index par mois, une recherche simple côté client sur les 30 derniers jours. Déploiement par l'action officielle Pages **une fois par édition** (pas à chaque collecte).

### 8.4 Envoi vers Mizeniti (phase 2)
`POST` du fichier d'édition vers le point d'entrée Mizeniti (secret `MIZENITI_INGEST_TOKEN`, à créer en phase 2). Échec = trois essais, puis alerte santé ; l'édition reste disponible sur la branche `data` pour reprise.

## 9. Stockage

- Branche `main` : code, configuration, workflows.
- Branche `data` : état (`state/vus.json` : liens déjà vus par source, 60 jours), articles du jour (`articles/AAAA-MM-JJ.jsonl`), éditions, compteur Claude, journal de santé. Écritures par commit du bot ; `concurrency` par workflow pour éviter les conflits ; purge des articles au-delà de 90 jours (les éditions sont conservées).
- Aucun fichier de données sur `main` : un commit de données ne relance rien.

## 10. Contrôle de santé

À 21:00 (et à la fin de chaque tâche pour ses propres erreurs) :
- source sans aucun article depuis N jours (N par type : 3 j ouvrés pour presse, 10 j pour INS, 7 j pour BCT, CMF, BVMT) ;
- tâche planifiée non exécutée ou en échec dans les dernières 24 h (lu via l'API GitHub du dépôt avec le jeton du workflow) ;
- édition manquante ; Gemini en échec et Claude utilisé ; plafond Claude à 80 % ;
- Yahoo Finance, traduction AWB sans donnée ;
- données de Bourse de Mizeniti périmées : date de séance antérieure au dernier jour ouvré à 21:00 (signale aussi si le repli direct a servi).

Message ⚠️ groupé, une ligne par anomalie, avec l'action suggérée. Le dimanche, message « ✅ Semaine complète » avec le nombre d'éditions et d'alertes.

## 11. Sécurité

- Dépôt public : aucun secret, aucune donnée personnelle, aucun e-mail dans le code ou les workflows.
- Secrets du dépôt : `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `TG_TOKEN_VEILLE`, `TG_CHAT_ID`, `MYMEMORY_MAIL` (facultatif, absent au 14/11), `MIZENITI_INGEST_TOKEN` (phase 2).
- ntfy abandonné (topic exposé).
- Permissions de workflow minimales par fichier (`contents: write` seulement là où l'état est écrit ; `pages: write` + `id-token: write` pour Pages).
- Actions tierces épinglées par version.

## 12. Consommation GitHub

Dépôt public : minutes gratuites. Cible : environ 35 exécutions par jour ouvré, moins de 2 minutes chacune en moyenne (cache pip). Budget Actions du compte machine à 0 $ (déjà en place) : aucun dépassement payant possible.

## 13. Bascule et retrait de l'existant

1. Le nouveau dépôt tourne seul pendant 7 jours (les anciens sont bloqués par le verrou du compte principal et ne tournent pas).
2. Bilan de la semaine (éditions, alertes, sources mortes).
3. Le porteur archive `sitemoussam`, `veille-bfi`, `veille-awb`, `veille-tunisie` (Settings → Archive), puis les supprime s'il le souhaite. **Claude Code ne supprime ni n'archive aucun dépôt.**
4. Les anciens sites Pages disparaissent avec les dépôts ; l'ancienne URL `veille-tunisie` n'est pas redirigée.

## 14. Livraisons

| Lot | Contenu |
|---|---|
| V0 Socle | Structure du dépôt, module commun (HTTP avec délais et nouveaux essais, Telegram avec découpage, IA Gemini→Claude avec plafond, état sur branche `data`, journal), configuration, tests, CI de tests |
| V1 Collecte et alertes | Lecteurs RSS / HTML générique / BCT / INS / CMF / BVMT / Google News, résolution et nettoyage des liens, déduplication, filtre éditorial, alertes avec plage silencieuse, workflow de collecte |
| V2 Synthèses | Classement et rédaction IA, fichier d'édition (schéma v1), Telegram, archive Pages, workflows des éditions |
| V3 Marchés | Lecture des données de Bourse de Mizeniti, repli direct sur les fichiers de la Bourse si accessible (§ 6.4), BCT (taux, cours), Yahoo (international), deux points marchés (Bourse 17:20, international 22:45), tableaux des chapitres 3 et 4 |
| V4 AWB | Reprise de `veille_awb.py` sur le socle (traduction, déduplication), workflow |
| V5 Santé et bascule | Contrôle de santé, message du dimanche, README d'exploitation, bilan de la première semaine |

## 15. Critères d'acceptation

| # | Critère |
|---|---|
| A1 | `pytest` vert, couverture des lecteurs BCT, INS, CMF, BVMT, RSS sur des pages enregistrées (fixtures HTML/XML anonymes, pas d'appel réseau en test) |
| A2 | Une collecte réelle (déclenchement manuel) ramène au moins un article de chaque source active, ou l'anomalie apparaît dans le rapport de santé |
| A3 | Une alerte BCT ou CMF arrive sur Telegram au passage suivant sa publication ; dans la plage 22:00–07:00, elle arrive à 07:00 |
| A4 | Une édition contient les chapitres non vides dans l'ordre du § 4, chaque sujet avec au moins un lien vers un article d'origine, aucun lien Google News non résolu, aucun paramètre `utm_` |
| A5 | Le fichier d'édition valide le schéma v1 ; une donnée absente vaut `null` |
| A6 | Un message Telegram de plus de 4 096 caractères est découpé sans balise cassée |
| A7 | Gemini simulé en échec : Claude prend le relais ; plafond simulé atteint : aucune requête Claude, alerte santé |
| A8 | Une source simulée muette au-delà de son délai apparaît dans le rapport de santé |
| A9 | Aucune donnée sur `main` ; aucune écriture concurrente perdue sur `data` (test de deux tâches simultanées) |
| A10 | Aucun secret, e-mail ou identifiant personnel dans le dépôt (scan des fichiers suivis) |
| A12 | Tout article en anglais ou en arabe, non payant, a une `url_traduite` qui ouvre la page traduite en français (contrôlé sur trois hôtes réels : un anglais, un arabe, un Google News résolu) ; titre affiché en français, titre d'origine conservé |
| A11 | Point Bourse : TUNINDEX et indice Banques présents avec variation signée et variation annuelle, date de séance affichée, chiffres identiques à `/marche/bourse/indices.json` de Mizeniti ce jour-là ; source absente = tiret explicite. Aucun appel à irbe7 ni à un rediffuseur (contrôlé dans le code) |
