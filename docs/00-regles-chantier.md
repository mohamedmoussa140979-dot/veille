# Chantier « Veille » — règles

Version du 14/11/2026. Deux dépôts, deux phases :

| Phase | Dépôt | Spec | Prompt |
|---|---|---|---|
| 1 — Veille | `mohamedmoussa140979-dot/veille` (public, neuf) | `spec-veille.md` | `PROMPT-MAITRE-veille.md` |
| 2 — Actualités dans Mizeniti | `abtmohamedmoussa-svg/pfm-platform` | `spec-actualites-mizeniti.md` | `PROMPT-MAITRE-actualites.md` |

Ordre de priorité : `CLAUDE.md` du dépôt > `docs/cadrage-global/00-regles-communes.md` (phase 2, s'il est présent) > ce document > la spec > `journal-decisions.md` pour les intentions du porteur.

La phase 2 ne démarre que si la phase 1 a livré V2 vert (éditions valides sur la branche `data`).

## 1. Le porteur

Il n'est pas développeur, ne relit pas le code, lit sur son téléphone. Ce qui le protège : les tests, les bilans écrits, la recette réelle. Retour factuel, sans complaisance : signaler ce qui est faible, flou ou inutile dans la spec. Une question à la fois, avec options et recommandation.

## 2. Phase 1 — dépôt `veille`

- Dépôt indépendant : aucun risque de conflit avec les sessions de `pfm-platform`. Une seule session Claude Code à la fois sur ce dépôt ; au démarrage, vérifier qu'aucune autre branche `v*-` n'est en cours (`git branch -r --no-merged main`) et lire `bilans/ETAT.md`.
- Clone de travail : `C:\Users\Admin\veille` (jamais sur le Bureau, jamais dans un dossier de `pfm-platform`). Une branche par lot (`v0-socle`, `v1-collecte`…), fusion dans `main` quand le lot est vert.
- Accès : le porteur pousse avec son compte principal `abtmohamedmoussa-svg`, collaborateur du dépôt. Si l'invitation n'est pas acceptée, la poussée échoue : cas d'arrêt (une phrase au porteur : accepter l'invitation sur `https://github.com/mohamedmoussa140979-dot/veille/invitations`).
- Python 3.12, dépendances épinglées (`requests`, `feedparser`, `beautifulsoup4`, `lxml`, `pyyaml`, `jsonschema`, `pytest`, `ruff`). Pas de navigateur headless sans le justifier au bilan.
- Tests sans réseau : fixtures HTML/XML enregistrées et anonymisées. Les essais réels se font par déclenchement manuel (`workflow_dispatch`) une fois le lot poussé, et sont notés au bilan.
- **Interdit de modifier les anciens dépôts** (`sitemoussam`, `veille-bfi`, `veille-awb`, `veille-tunisie`) : lecture seule, pour reprendre la logique utile. Ne pas les archiver ni les supprimer.

## 3. Phase 2 — dépôt `pfm-platform`

D'autres sessions travaillent en même temps dans ce dépôt et publient dans la même recette (au 14/11 : affectation `ca-*`, cadrage global `cg-*`, agios `ag-*`, SMS `sm-*`, Marché `claude/lot-marche`, multi-appareil). La liste n'est pas figée.

1. **Ne jamais toucher au dépôt principal** `C:\Users\Admin\Desktop\pfm-platform` (pas de `checkout`, `stash`, `clean`, `add -A`, `npm install`). Worktree `C:\Users\Admin\pfm-wt\ac-<lot>`, branche `ac-<lot>` partie de `deploy` à jour ; fichiers de travail dans `C:\Users\Admin\pfm-travail\ac-<lot>\`.
2. **Propriété du chantier** : `apps/actualites/` (nouveau), `apps/mobile/app/actualites*.tsx`, `apps/mobile/src/actualites/`, `apps/mobile/src/i18n/locales/*/actualites.json`, `apps/backoffice/src/**/veille*` (nouveaux fichiers), `docs/aide/actualites.md`, et leurs tests.
3. **Fichiers des autres, interdits sauf une ligne** : `apps/market-data/` (Marché), écran Marché, écran Crédits, Accueil, menu Plus.

## 4. Zones partagées (phase 2) et matrice

| Zone | Fichiers | Ce que le chantier y fait | Propriétaire actuel probable |
|---|---|---|---|
| Z1 | Menu Plus / navigation | Une entrée « Actualités » à côté de « Marché » | Cadrage global, SMS (une ligne chacun) |
| Z2 | Accueil (zone de trois cartes) | Une carte « L'essentiel du matin » | Cadrage global lot 2 (refonte de l'Accueil) |
| Z3 | Écran Marché | Une ligne de lien vers le chapitre 3 | Chantier Marché |
| Z4 | Écran Crédits | Une ligne de lien vers le sujet TMM | Cadrage global lot 1b |
| Z5 | `scripts/deploy-recette.mjs` | Étape de déploiement de `apps/actualites` | Partagé |
| Z6 | Tâche planifiée hôte (purge, déclenchement) | Un appel de service d'une ligne | À identifier (licences ou push) |
| Z7 | `e2e/garde-fou-ecrans.spec.ts`, `scripts/ecrans-impactes.json` | Ajout de lignes | Partagé (fusion, jamais motif d'attente) |

**Matrice a priori** : AC1 (serveur) ne touche que Z5 et Z6 → contrôler. AC2 (écrans) touche Z1 à Z4 → **attendre** si le lot 2 du cadrage global (Accueil) ou un lot Marché touchant l'écran Marché est en cours ; dans ce cas, livrer l'écran Actualités et le menu Plus, et mettre la carte d'Accueil et les liens croisés « en attente ». AC3 (back-office) : contrôler `apps/backoffice`.

**Une carte d'Accueil ou un lien croisé en attente ne bloque pas la publication du reste** : ils font l'objet d'un petit lot de raccord (`ac-raccords`) après la fusion de la branche attendue.

## 5. Contrôle du risque de conflit (phase 2, obligatoire)

Au démarrage de chaque session, après l'inventaire de chaque lot, avant tout changement en zone Z1 à Z6, juste avant la publication :
- `git fetch --all --prune` ; `git worktree list` ; `git branch --all --no-merged deploy` ;
- pour chaque branche modifiée depuis moins de 7 jours : `git diff --name-only $(git merge-base deploy <branche>) <branche>` ;
- intersection avec l'inventaire du lot ; résultat daté dans `docs/chantier-veille/bilans/CONFLITS.md`.

Intersection vide : on avance. Non vide : les changements sans fichier commun se font, les autres sont « en attente de <branche> » ; quand il ne reste que de l'attente, la session s'arrête avec un message d'une phrase. Une attente ne se contourne pas (pas de copie de leurs fichiers, pas de fusion de leur branche).

**Une seule recette** : lire la dernière ligne du journal des déploiements ; si elle vient d'une branche non fusionnée, s'arrêter ; si le dossier de déploiement a bougé dans les dix dernières minutes, attendre et relire.

## 6. Secrets et accès

- Phase 1 : secrets déjà posés (`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `TG_TOKEN_VEILLE`, `TG_CHAT_ID`). Ne jamais les lire, les afficher ni les écrire.
- Phase 2 : `MIZENITI_INGEST_TOKEN`, `VEILLE_CONFIG_TOKEN`, `GITHUB_DISPATCH_TOKEN` sont créés et posés **par le porteur**. Besoin d'un secret absent : développer et tester par simulation, puis arrêt avec la question.
- Aucun secret, e-mail ou identifiant personnel dans un dépôt.

## 7. Interdits

- Bourse : jamais irbe7, ilboursa ni un autre rediffuseur ; jamais de modification de `marche-jobs` ou du Worker `marche-lecture` (lecture HTTP seulement, V42).

- Production Mizeniti gelée : aucun `wrangler deploy` sans `-c` vers un `wrangler.recette.jsonc` ; jamais `JE_DEPLOIE_LA_PRODUCTION` ; jamais de poussée sur `origin/master`.
- Ne jamais contourner un test (désactivation, seuil relevé) ni une attente.
- Aucune reproduction de texte d'article ; aucune image de presse.
- Aucune action sur la facturation GitHub ou Cloudflare.
- Aucune suppression ni archivage de dépôt.

## 8. Ce que Claude Code ne peut pas vérifier

Rendu sur iPhone, ouverture des liens dans la PWA installée, réception Telegram. Chaque bilan liste cinq points au plus que le porteur regarde sur son téléphone.
