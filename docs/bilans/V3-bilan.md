# Bilan — V3 marchés — 15/11/2026

## En une phrase
Le point Bourse (17:20, nouvel essai 18:20), la clôture internationale (22:45), les tableaux des chapitres 3 et 4 et les quatre chiffres de l'édition sont en place : la Bourse et les taux BCT viennent de Mizeniti (lecture seule), l'international de Yahoo ; trois limites sont documentées (MASI, fiche BVMT par valeur, repli direct).

## Fait
- **Source de Bourse : le Worker `marche-lecture` de Mizeniti**, lu en HTTP anonyme et seul (V42). Adresse trouvée dans les scripts de déploiement de Mizeniti (elle n'est pas dans le README de `marche-jobs`) et rangée dans `config/parametres.yaml`. Même chiffres que l'application.
- **Point Bourse** : TUNINDEX, TUNINDEX20 et indice Banques (valeur, variation du jour, variation depuis le 1er janvier telles que publiées), trois plus fortes hausses et baisses (valeurs non cotées du jour ignorées), capitaux échangés et transactions, mention « provisoire » si Mizeniti la sert, date de séance. Aucun appel à irbe7 ni à un rediffuseur (contrôlé par un test sur le code).
- **Nouvel essai** : à 17:20 rien n'est envoyé si la séance du jour n'est pas encore publiée ; à 18:20, message « Séance du JJ/MM non encore publiée » (avec la dernière séance disponible) ; source muette = message explicite, jamais de chiffre inventé. Pas de message le week-end ni les jours de `config/jours_feries.yaml`. Anti-doublon : un seul point Bourse par jour.
- **Clôture internationale** : Brent, gaz naturel, or, blé ; S&P 500, Euro Stoxx 50, CAC 40, MASI ; EUR/USD ; cours moyens BCT EUR/TND et USD/TND ; TMM. Une donnée absente garde sa ligne avec un tiret.
- **Édition** : chapitre 3 = tableau Bourse, chapitre 4 = tableau international, chacun avec liens vers sa source ; les quatre chiffres de l'en-tête Mizeniti (TUNINDEX, EUR/TND BCT, Brent, TMM) sont renseignés, `null` si la source est muette. Un chapitre sans sujet garde son tableau (le contrat v1 est assoupli : `sujets` peut être vide quand `tableau` est présent). Rendu dans le message Telegram et dans l'archive. Une panne des marchés ne bloque jamais l'édition.
- **Workflow `marches`** : crons de la spec § 5, point et essai lus dans l'horaire, options d'essai manuel (`point`, `essai`, `jour`).

## Vérifié, et comment
| Critère | Commande ou contrôle | Résultat |
|---|---|---|
| A11 — TUNINDEX et indice Banques présents avec variation signée et variation annuelle, date de séance, chiffres identiques à `indices.json` | Test : valeurs et variations comparées à la réponse enregistrée de `/marche/bourse/indices.json` ; **point réel sur un runner GitHub** (séance du 13/11) : TUNINDEX 18 989,99 (+0,79 %, depuis le 1er janvier +41,19 %), Indice des Banques 14 427,85 (+0,96 %, +49,21 %) | Vert |
| A11 — source absente = tiret explicite | Tests : Worker muet, séance non publiée, instrument Yahoo en panne | Vert |
| A11 — aucun appel à irbe7 ni à un rediffuseur (contrôlé dans le code) | `test_a11_aucun_rediffuseur_dans_le_code_des_marches` | Vert |
| Mizeniti lisible anonymement, mêmes routes (inventaire M1) | 6 routes en HTTP 200, depuis un poste et depuis un runner GitHub | Vert |
| Yahoo depuis un runner GitHub | Point international réel : 8 instruments sur 9 (le MASI n'a pas de symbole Yahoo) | Vert |
| CI | `ruff` et plus de 230 tests ; CI verte | Vert |

## Essai réel (workflow, journal, résultat constaté)
- Exécution 43654914754 : point Bourse (séance du 13/11 imposée, un samedi-dimanche n'ayant pas de séance) : message envoyé, contenu conforme (voir ci-dessus).
- Exécution 43654947526 : clôture internationale envoyée (Brent 95,84 USD, S&P 500 7 561,67, EUR/TND BCT 3,3639, TMM 7,00 %…).
- Exécution 43654996406 : édition avec tableaux et chiffres (voir « Non vérifié » pour ce qui reste à constater).

## Non vérifié
- **Premiers passages planifiés** (lundi 17:20, 18:20 et 22:45) : horaires réels, nouvel essai de 18:20, anti-doublon.
- **Heure de publication de Mizeniti** : la spec annonce des passages vers 16:30, 18:00 et 21:40 ; le point de 17:20 suppose le premier passage. Si Mizeniti publie plus tard, l'essai de 18:20 prend le relais.
- **Rendu sur le téléphone** des messages 📈 et des tableaux de l'édition.
- **Fêtes religieuses mobiles** : absentes de `jours_feries.yaml` (à compléter chaque année).

## Écarts à la spec
- § 6.4 : **le repli direct sur le site de la Bourse n'est pas construit**. Mizeniti est la seule source de Bourse et de taux BCT (la spec le prévoyait seulement si un runner GitHub accédait au site de la Bourse, test non fait faute d'utilité). Muette = tiret + événement de santé.
- § 4 chapitre 3 : « chaque ligne mène à sa source (**fiche BVMT de la valeur**) » : **aucune adresse de fiche par valeur n'a été trouvée** sur le site de la Bourse ; chaque ligne renvoie vers la liste des émetteurs (`https://tunis-stockexchange.com/emetteurs`). À corriger si vous connaissez le modèle d'adresse d'une fiche.
- § 4 chapitre 4 : **MASI sans source** (aucun symbole Yahoo, aucun flux Mizeniti) : ligne présente, valeur à tiret. Le contrat v1 est assoupli pour un chapitre qui n'a que son tableau.
- § 6.1 « BCT (taux, cours) » lus chez Mizeniti plutôt que sur la page `index.jsp` de la BCT : mêmes valeurs, source BCT affichée.
- Taux directeur de la BCT : non repris (la spec ne le demande dans aucun tableau).

## Choix faits sans le porteur
- Variation du jour de TUNINDEX20 et de l'indice Banques **calculée** à partir de la valeur précédente quand Mizeniti ne la sert pas (indices à fréquence mensuelle) ; marquée comme calculée dans les données (`variation_calculee`), sans mention à l'écran.
- Capitaux affichés en millions de dinars, valeurs en dinars à trois décimales, variations avec le vrai signe moins.
- Les points ont leur propre en-tête 📈 ; l'essai manuel `jour` n'écrit rien dans l'état.

## À regarder sur le téléphone (cinq points au plus)
1. Message « 📈 Marchés » Bourse : TUNINDEX 18 989,99, hausses et baisses, capitaux 20,74 MTND ; les noms de valeurs sont cliquables (liste des émetteurs de la Bourse).
2. Message « 📈 Marchés » clôture internationale : les 11 lignes, MASI en tiret.
3. L'édition : dans « Bourse, entreprises… » une ligne « Bourse de Tunis · séance du 13/11/2026 » puis TUNINDEX ; dans « Économie et marchés internationaux », les trois lignes Matières premières, Indices, Devises.
4. Les chiffres sont-ils ceux que vous attendez (TUNINDEX, EUR/TND, Brent, TMM) ?
5. Lundi : un seul message Bourse vers 17:20 (ou « non encore publiée » à 18:20), un seul message international à 22:45.

## Suite
V4 (AWB) : reprise de `veille_awb.py` sur le socle : requêtes, GDELT, Finextra, déduplication, traduction, message 🏦 deux fois par jour.
