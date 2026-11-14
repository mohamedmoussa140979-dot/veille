# Prompt maître — phase 1 : dépôt `veille`

À donner tel quel à Claude Code sur le PC du porteur. Il enchaîne les lots V0 à V5 tant que tout est vert et s'arrête au premier échec.

---

## Ta mission

Tu construis la veille économique consolidée dans le dépôt public `mohamedmoussa140979-dot/veille`, selon :

| Fichier | Rôle |
|---|---|
| `docs/00-regles-chantier.md` | Règles du chantier (§ 2 pour cette phase), interdits |
| `docs/spec-veille.md` | Spec validée (ligne éditoriale, chapitres, horaires, sources, IA, sorties, santé, critères A1 à A12) |
| `docs/journal-decisions.md` | Décisions du porteur V1 à V42 |

Six lots dans cet ordre : V0 socle, V1 collecte et alertes, V2 synthèses, V3 marchés, V4 AWB, V5 santé et bascule (spec § 14).

Les anciens dépôts (`abtmohamedmoussa-svg/sitemoussam`, `veille-bfi`, `veille-awb`, `veille-tunisie`) sont publics : clone-les **en lecture seule** dans `C:\Users\Admin\veille-anciens\` pour reprendre ce qui marche (lecteurs CMF et BVMT de `monitor.py`, découverte des modèles Gemini de `digest.py`, `resoudre_lien` et traduction de `veille_awb.py`, BCT et Yahoo de `summary.py`). Ne les modifie pas.

## Avant de commencer (à chaque session)

1. Si `C:\Users\Admin\veille` n'existe pas : `git clone https://github.com/mohamedmoussa140979-dot/veille C:\Users\Admin\veille`. Première session : copie les quatre fichiers de ce chantier dans `docs/`, commite-les sur `main`.
2. Lis `docs/00-regles-chantier.md` (§ 1, 2, 6, 7, 8), puis `docs/bilans/ETAT.md` s'il existe : reprends le lot en cours ; sinon crée-le et commence par V0.
3. `git fetch --all --prune` ; `git branch -r --no-merged main` : si une autre branche de lot est en cours sans être la tienne, arrête-toi et dis-le.
4. Lis dans la spec les sections du lot en cours, pas tout.

## Déroulé d'un lot

1. Branche `v<n>-<nom>` partie de `main` à jour.
2. **Inventaire** avant tout code : ce que tu reprends des anciens scripts, hypothèses de la spec à vérifier (ex. adresse du Worker `marche-lecture` de Mizeniti et accès direct au site de la Bourse depuis un runner GitHub, forme `translate.goog`), écrit dans `docs/bilans/<lot>-inventaire.md`. Une hypothèse fausse se corrige dans la spec, dans le même commit, et se note au bilan.
3. Découpe en petits changements listés dans `ETAT.md`.
4. Pour chaque changement : test d'abord (fixtures, pas de réseau), code, `ruff check`, `pytest`. Un commit par changement ; dépôt toujours fonctionnel.
5. Vérifie un par un les critères d'acceptation du lot. « Vert » = résultat complet lu, zéro échec.
6. Pousse la branche, fusionne dans `main`, déclenche manuellement le ou les workflows du lot (`gh workflow run`), lis leurs journaux, vérifie le résultat réel (message Telegram reçu ? fichier d'édition valide sur `data` ? page Pages publiée ?). Ce que tu ne peux pas constater toi-même va dans « À regarder sur le téléphone ».
7. Écris le bilan `docs/bilans/<lot>-bilan.md`, mets à jour `ETAT.md` et `README.md` (exploitation : ce que fait chaque workflow, comment le relancer, comment ajouter une source).
8. Enchaîne si tout est vert. Sinon, arrête-toi.

## Précisions par lot

**V0 — socle.** Module commun unique pour : HTTP (délais, nouveaux essais, en-têtes navigateur, encodage des URL), Telegram (un bot, en-têtes du § 8.1, découpage sur frontières de paragraphe, repli texte brut), IA (Gemini avec découverte des modèles et repli, puis Claude en secours avec plafond mensuel et compteur), état sur la branche `data` (lecture, écriture avec reprise sur conflit), journal. CI de tests sur `push` (pas de cron). Critères A6, A7, A9, A10.

**V1 — collecte et alertes.** Lecteurs `rss` (feedparser), `html-generique`, `bct`, `ins`, `cmf`, `bvmt`, `google-news` ; résolution des liens Google News ; nettoyage des paramètres de suivi ; `url_traduite` pour l'anglais et l'arabe non payants ; déduplication ; filtre des mots exclus ; alertes 🔔 pour les sources `alerte: oui` avec plage silencieuse 22:00–07:00 ; workflow de collecte aux horaires du § 5. Critères A1, A2, A3, A12.

**V2 — synthèses.** Classement et rédaction par l'IA en JSON validé ; fichier d'édition conforme à `schema/edition.v1.json` ; Telegram 🌅/🌆 ; archive Pages (une publication par édition) ; workflows matin, soir, week-end. Les tableaux des chapitres 3 et 4 restent vides (tiret) jusqu'à V3. Critères A4, A5. **Fin de V2 : écris dans `ETAT.md` « Phase 2 possible » ; elle se lance dans `pfm-platform` avec son propre prompt.**

**V3 — marchés.** Bourse de Tunis selon la spec § 6.4 : d'abord les routes `/marche/bourse/*` du Worker `marche-lecture` de Mizeniti (lecture seule), repli direct sur les fichiers publics de la Bourse seulement si un runner GitHub y accède (testé à l'inventaire). **irbe7, ilboursa et les autres rediffuseurs sont interdits**, même en repli. BCT (taux, cours) ; Yahoo (international) ; deux points 📈 (Bourse 17:20, international 22:45 ; plus de point de mi-séance) ; tableaux des chapitres 3 et 4 et quatre chiffres de l'édition. Critère A11.

**V4 — AWB.** Reprise de `veille_awb.py` sur le socle : requêtes, GDELT, Finextra, déduplication, traduction ; message 🏦 deux fois par jour.

**V5 — santé et bascule.** Contrôle du § 10 de la spec, message ⚠️, message du dimanche ; critère A8 ; README final ; après 7 jours de fonctionnement réel, bilan de la semaine (éditions produites, alertes, sources muettes, consommation Claude) et rappel au porteur d'archiver les quatre anciens dépôts lui-même.

## Quand t'arrêter

Arrête-toi, écris l'état et le bilan, et pose **une** question précise (options + recommandation) dès que :
- un critère est rouge et ne se corrige pas sans sortir de la spec ;
- la spec contredit une décision du porteur (V1 à V42) ;
- tu aurais besoin d'un secret, d'un mot de passe, d'un code ou d'un accès que tu n'as pas ;
- la poussée vers le dépôt est refusée (invitation non acceptée) ;
- une source essentielle (BCT, INS, CMF) n'est lisible qu'avec un navigateur ;
- les routes Bourse de Mizeniti sont introuvables ou inaccessibles sans authentification.

Un écart technique sans effet sur une décision du porteur ne t'arrête pas : corrige la spec, note-le au bilan.

## Modèle de bilan

```
# Bilan — <lot> — <date>
## En une phrase
## Fait
## Vérifié, et comment
| Critère | Commande ou contrôle | Résultat |
## Essai réel (workflow, journal, résultat constaté)
## Non vérifié
## Écarts à la spec
## Choix faits sans le porteur
## À regarder sur le téléphone (cinq points au plus)
## Suite
```

Commence maintenant par « Avant de commencer ».
