# Bilan AC3 — morceau « dépôt veille » (pilotage depuis Mizeniti)

Branche `ac3-pilotage` (partie de `main` à jour, **non fusionnée**). Contrat qui fait foi : `contrat-pilotage-veille.md` v1 du 15/11/2026 (dépôt `pfm-platform`, lu seulement). Rédigé le 15/11/2026.

## En une phrase

La veille sait lire sa configuration chez Mizeniti, envoyer ses éditions à l'application et répondre au bouton « Tester » d'une source ; **rien de cela n'a été essayé pour de vrai** (aucun jeton posé, aucun Worker interrogé). Tout est vérifié par des tests sans réseau.

## Fait

| # | Livrable | Où |
|---|---|---|
| 1 | Schéma du document de configuration et lecteur avec repli | `schema/config.v1.json`, `veille/config_distante.py`, `mizeniti.actualites_url` dans `config/parametres.yaml` |
| 2 | Branchement : sources actives, mots exclus, plage silencieuse (avec minutes), plafond Claude | `veille/collecte/__main__.py`, `alertes.py`, `orchestrateur.py`, `veille/ia.py`, `veille/config.py`, `veille/edition/__main__.py`, `veille/sante/__main__.py` |
| 3 | Envoi des éditions | `veille/edition/envoi.py` (appelé par `veille/edition/__main__.py`) |
| 4 | Mode test de source | `veille/collecte/essai_source.py`, options `--source-test` / `--demande-id` |
| 5 | Workflows : entrées `source_test`, `demande_id`, jetons | `collecte.yml`, `edition.yml`, `sante.yml` (**aucun cron touché**) |
| – | Santé : trois nouvelles anomalies (repli de configuration, édition non envoyée, source ignorée) | `veille/sante/controle.py` (`controle_pilotage`) |
| – | Sélecteur CSS des sources `html-generique` (champ `selecteur` du contrat, qui n'existait pas encore) | `veille/collecte/lecteurs/html_generique.py` |

Un commit par changement : configuration distante, branchement, envoi, mode test, workflows, README.

### Comportements à connaître

- **Repli** : jeton absent, réseau, 404, 401/403, 5xx, délai de 10 s (2 essais), JSON illisible, version ≠ 1, document hors schéma, identifiants de source en double, erreur inattendue → fichiers locaux, la collecte continue. Jeton absent = information seulement ; les autres cas = avertissement `config_distante_repli`. Le message ne contient que le code, le nom du champ fautif et la règle, **jamais la valeur reçue ni le jeton** (testé avec des valeurs piège).
- **Source d'un type inconnu** : ignorée, avertissement `config_source_ignoree` (id seulement), le reste du document est utilisé. Pour cela, `type` n'est volontairement pas une énumération dans `config.v1.json`.
- **Le document fait foi** quand il est lu : une source active des fichiers locaux **absente du document n'est plus collectée** (information `config_sources_locales_absentes` au journal de la tâche). Le document d'amorce côté serveur doit donc contenir toutes les sources.
- **Filtre éditorial** : le document ne remplace que `mots_exclus` ; `expressions_conservees` (ex. « guerre commerciale ») et `segments_url_exclus` restent lus depuis `config/exclusions.yaml`. C'était déjà le cas ; prouvé par un test (ajouté après relecture, aucune correction de code nécessaire).
- **Plafond Claude** : le document l'emporte sur la variable du dépôt `CLAUDE_PLAFOND_USD_MOIS` (qui reste utilisée en repli).
- **Envoi des éditions** : après Telegram, avant l'archive Pages (qui est un autre job). Trois essais sur réseau, 429 et 5xx ; un 4xx n'est pas réessayé ; tout 2xx = succès. L'échec ne change **pas** le code de sortie (sinon le job `pages` serait sauté) : il est écrit au journal de santé (`ingest_echec`) et le contrôle de 21:00 le signale dès le premier.
- **Santé** : le repli de configuration n'alerte qu'à partir de 2 passages en 24 h (un accroc isolé ne réveille personne) ; l'édition non envoyée alerte dès la première.
- **Mode test** : ne lit que la source demandée (config distante d'abord, pour connaître une source ajoutée au back-office), aucune alerte, `EtatGit` jamais ouvert (aucun état modifié), résultat renvoyé même en cas d'échec (`ok: false`, erreur en français). Source inconnue / inactive / de type ignoré / identifiant invalide → `ok: false`. Sans jeton : une demande réelle échoue (code 1, visible dans Actions) ; un essai local (sans `demande_id`) n'envoie rien. Un essai a son **propre groupe de concurrence** : il ne peut pas faire annuler une collecte planifiée en attente.

## Vérifié, et comment

- **362 tests verts** (`pytest`, 2 min 54), **`ruff check` et `ruff format --check` propres**, sur la branche à l'état final. Aucun test n'ouvre de réseau (garde-fou existant). Commandes : `.venv/Scripts/python.exe -m pytest tests -q` et `.venv/Scripts/python.exe -m ruff check .` depuis `C:\Users\Admin\veille`.
- Nouveaux fichiers de tests : `test_config_distante.py` (32 cas : nominal, URL et en-têtes de l'appel, 10 causes de repli, aucun jeton ni contenu dans le journal, type inconnu, doublons, bornes du schéma), `test_ac3_branchement.py` (plage silencieuse, sélecteur, santé, points d'entrée), `test_envoi_edition.py`, `test_essai_source.py`, `test_workflows_ac3.py` (crons attendus inchangés, jetons passés par l'environnement).
- Une lecture réelle d'une source publique (`business-news`, 10 articles) en mode test local, sans jeton : le résultat s'affiche, rien n'est envoyé, aucun fichier d'état créé.
- Fichiers YAML des workflows relus par un analyseur YAML (syntaxe valide).

## NON vérifié (à dire clairement)

- **Aucun appel réel** à `GET /veille/config`, `POST /actualites/ingest` ni `POST /veille/resultat-test` : aucun jeton n'a été lu ni utilisé, le Worker n'a pas été interrogé. Les formes d'appel sont celles du contrat, jamais confrontées au vrai Worker.
- **Aucun workflow GitHub exécuté** avec les nouvelles entrées ou les jetons. La syntaxe des expressions `${{ … }}` (groupe de concurrence, entrées vides sur les passages planifiés) est relue mais **non éprouvée par GitHub**.
- Les réponses réelles du Worker (codes 2xx exacts, 409 éventuel sur une édition déjà reçue) sont supposées : on tient tout 2xx pour un succès.
- Les messages Telegram ⚠️ des trois nouvelles anomalies n'ont pas été envoyés ni vus sur un téléphone.
- La CI du dépôt (`tests.yml`) : voir « Poussée » en bas.

## Écarts au contrat et au brief

1. **`conservation_mois` est lu et validé mais n'est branché nulle part** : d'après la spec Actualités (§ 3.2, `actu.retention_mois`), c'est la conservation des éditions **dans le Worker**. Côté veille, les éditions sont conservées sans limite sur `data` et la purge des articles reste à 90 jours (spec veille § 9). *Question au contrat :* faut-il que la valeur pilote aussi la purge des articles ? Je ne l'ai pas supposé.
2. **`horaires` (collectes, éditions) : validés mais non consommés** ; seule `plage_silencieuse` agit. Les heures de collecte et d'édition sont celles du Worker (déclenchement) ; la veille n'a rien à en faire tant que les crons existent.
3. **`type` des sources non énuméré dans le schéma** (voir plus haut), nécessaire pour « ignorée et signalée, pas fatale ». Les autres champs énumérés (`chapitre`, `langue`) invalident le document entier s'ils sont hors liste, comme le contrat les fixe.
4. **Le contrat ne dit pas** ce que fait la veille d'une source locale absente du document (choix : non collectée), ni si le document l'emporte sur `CLAUDE_PLAFOND_USD_MOIS` (choix : oui). À confirmer.
5. **`sante.yml` reçoit aussi `VEILLE_CONFIG_TOKEN`** (non listé au brief) : sans cela, le contrôle de 21:00 jugerait les sources avec les fichiers locaux et signalerait comme « muettes » des sources désactivées au back-office.
6. **`selecteur`** : le champ existe au contrat mais aucun lecteur ne l'employait ; ajouté pour `html-generique` seulement (ignoré pour les autres types).
7. **Liens Google News non résolus en mode test** (liens renvoyés tels quels, d'où des URL `news.google.com` possibles dans le résultat).

## Faiblesses connues

- **Un workflow ne peut être déclenché que s'il existe sur `main`** : tant que `ac3-pilotage` n'est pas fusionnée, `source_test` n'existe pas pour GitHub, et le bouton « Tester » (comme tout déclenchement par `workflow_dispatch` avec ces entrées) ne marchera pas. La fusion est décidée par le porteur.
- `edition.yml` recopie encore l'entrée `heures` dans la commande (`run: … --heures ${{ inputs.heures }}`) : existant, non modifié ; risque faible (déclencher un workflow exige déjà le droit d'écriture), mais mieux vaudrait la passer par l'environnement.
- Un seul document de configuration par passage et 2 essais de 10 s : en panne du Worker, chaque collecte perd jusqu'à ~25 s.
- Pas de mémoire entre deux passages : un repli puis un retour à la normale peuvent faire apparaître un jour une source désactivée au back-office comme « réactivée » le temps d'un passage.
- L'envoi d'une édition n'est pas rejoué automatiquement après les trois essais : relancer le workflow `edition` (type et heures) renvoie, l'ingestion étant idempotente d'après le contrat.

## Retrait des crons : préparation pour le porteur (rien n'a été retiré)

À ne faire **qu'une fois** : `GITHUB_DISPATCH_TOKEN` posé côté Worker, mode `reel` constaté au back-office, une collecte et une édition déclenchées avec succès depuis Mizeniti, **et la branche `ac3-pilotage` fusionnée dans `main`** (sinon les entrées n'existent pas côté GitHub).

Lignes exactes à retirer (numéros de la branche `ac3-pilotage` ; garder `workflow_dispatch`) :

| Fichier | Lignes | Contenu |
|---|---|---|
| `.github/workflows/collecte.yml` | 8 à 11 | `# Lun–ven : …`, `- cron: "15 6,8,10,12,14,16,19 * * 1-5"`, `# Sam–dim : …`, `- cron: "15 8,17 * * 0,6"` (et donc tout le bloc `schedule:` ligne 7) |
| `.github/workflows/edition.yml` | 7 à 9 | `- cron: "30 6 * * 1-5"`, `- cron: "30 17 * * 1-5"`, `- cron: "30 8 * * 0,6"` (et le bloc `schedule:` ligne 6) |

À **garder** (le contrat ne déclenche que `collecte` et `edition`) : `marches.yml` (3 crons), `awb.yml` (1 cron), `sante.yml` (`0 20 * * *`).

Attention : tant que les crons d'édition existent, `EDITION_SCHEDULE` fixe le type ; sans cron, le type vient de l'entrée `type` envoyée par Mizeniti (ou, si `auto`, de l'heure). Le Worker doit donc toujours envoyer `type`.

**Cron de secours quotidien (« une édition a-t-elle été produite ? »)** : le contrôle de santé de 21:00 (`sante.yml`, cron `0 20 * * *`) fait déjà ce travail — `controle_editions` signale « Édition matin/soir du JJ/MM absente » et `controle_taches` « le workflow edition n'a pas réussi depuis plus de 25 h ». **Je propose de ne rien ajouter** : le texte du cron de secours est celui qui existe déjà :

```yaml
# sante.yml — inchangé
on:
  schedule:
    - cron: "0 20 * * *"   # 21:00 Tunis : édition du jour manquante ⇒ message ⚠️
```

Ce cron **détecte** mais ne **produit** pas d'édition. Si le porteur veut que le secours produise une édition quand Mizeniti est muet, il faudrait ajouter une option `--si-absente` à `python -m veille.edition` et un cron `45 6 * * 1-5` (07:45 Tunis) dans `edition.yml` : **non fait**, hors du périmètre demandé (« vérifie »).

## À regarder sur le téléphone (cinq points au plus)

Rien n'a été vu sur un téléphone par moi ; ce sont les premiers constats utiles après la pose des jetons et la fusion.

1. Le message ⚠️ de 21:00 : une ligne « Configuration de Mizeniti illisible… fichiers locaux utilisés » n'est **pas** normale après la pose de `VEILLE_CONFIG_TOKEN` ; si elle apparaît, la raison entre parenthèses dit quoi corriger (404 = jeton absent côté Worker).
2. Le même message : « N édition(s) non envoyée(s) à Mizeniti (HTTP …) » — attendu seulement si le Worker est tombé ou le jeton refusé ; Telegram et l'archive doivent rester normaux.
3. Les alertes de nuit : l'en-tête « Détectées pendant la plage silencieuse (22:00–07:00) » doit rester identique (il affichera la plage du back-office si elle change).
4. Dans l'application : l'édition du matin (07:30) doit apparaître dans Actualités peu après le message Telegram du matin.
5. Au back-office, après fusion : le bouton « Tester » d'une source doit afficher ses articles en moins de quelques minutes ; une source désactivée doit afficher « Source inactive… ».

## Poussée

Voir le rapport de fin de session : la branche `ac3-pilotage` est poussée sur `origin` pour que `tests.yml` tourne ; aucun workflow avec secrets n'a été déclenché et `main` n'a pas été touché.
