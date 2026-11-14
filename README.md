# veille

Veille économique consolidée (Tunisie, Afrique, international) : alertes immédiates, deux synthèses par jour, points marchés, veille AWB. Dépôt public, exécuté par GitHub Actions.

Tout est décrit dans `docs/` : règles du chantier (`00-regles-chantier.md`), spécification (`spec-veille.md`), décisions du porteur (`journal-decisions.md`). L'avancement est dans `docs/bilans/ETAT.md`, un bilan par lot dans `docs/bilans/`.

## État

Lots V0 (socle), V1 (collecte et alertes), V2 (synthèses) et V3 (marchés) livrés (bilans dans `docs/bilans/`). Les workflows d'AWB et de santé arrivent avec les lots V4 et V5. Archive publique : https://mohamedmoussa140979-dot.github.io/veille/

## Ce que fait chaque workflow

| Workflow | Déclenchement | Rôle |
|---|---|---|
| `tests` | à chaque `push` (hors branche `data`) | `ruff` + `pytest`, sans réseau |
| `smoke` | manuel (`Actions` → `smoke` → *Run workflow*) | Essai réel : branche `data`, Gemini, Claude, Telegram. Case « tester_claude » : un appel Claude minimal (quelques millièmes de dollar) |
| `collecte` | planifié (heure de Tunis) : lun–ven 07:15, 09:15, 11:15, 13:15, 15:15, 17:15, 20:15 ; sam–dim 09:15 et 18:15 ; manuel possible | Lit les 49 sources, résout les liens, filtre, déduplique, écrit les articles du jour sur `data`, envoie les alertes 🔔 (plage silencieuse 22:00–07:00 : envoi groupé à 07:00). Case « essai_alerte » : envoie deux alertes d'exemple et ne collecte rien |

| `edition` | planifié (heure de Tunis) : lun–ven 07:30 (matin) et 18:30 (soir), sam–dim 09:30 (week-end) ; manuel possible | Classe et rédige la synthèse avec l'IA (Gemini, Claude en secours), écrit `editions/AAAA-MM-JJ-matin|soir.json` sur `data`, envoie le message 🌅/🌆 et publie l'archive sur GitHub Pages. Entrées manuelles : `type` (auto, matin, soir, weekend), `heures` (fenêtre forcée) |

| `marches` | planifié (heure de Tunis, jours ouvrés) : 17:20 point Bourse, 18:20 nouvel essai si la séance du jour n'est pas encore publiée, 22:45 clôture internationale ; manuel possible | Point 📈 : Bourse de Tunis (TUNINDEX, indice Banques, trois plus fortes hausses et baisses, capitaux) lue chez Mizeniti en lecture seule ; clôture internationale (Yahoo Finance) et cours BCT. Entrées manuelles : `point`, `essai`, `jour` (essai avec un jour imposé, sans anti-doublon) |

Relancer un essai depuis un terminal :

```bash
gh workflow run smoke.yml -R mohamedmoussa140979-dot/veille
gh workflow run collecte.yml -R mohamedmoussa140979-dot/veille
gh workflow run collecte.yml -R mohamedmoussa140979-dot/veille -f essai_alerte=true
gh workflow run edition.yml -R mohamedmoussa140979-dot/veille -f type=matin -f heures=24
gh workflow run marches.yml -R mohamedmoussa140979-dot/veille -f point=bourse -f essai=2 -f jour=2026-11-13
```

Essai local sur de vraies pages, sans Git ni Telegram (état dans `_etat_local/`) :

```bash
.venv/Scripts/python -m veille.collecte --a-blanc
```

### Ajouter, modifier ou désactiver une source

Dans `config/sources.yaml` : copier une entrée de même type, changer `id`, `nom`, `url`. Type `rss` si le site publie un flux, `html-generique` sinon ; `google-news` pour un flux de recherche Google News. `alerte: true` pour une alerte immédiate, `payant: true` pour la pastille 🔒 (pas de lien traduit), `langue` en `fr`, `en` ou `ar`, `actif: false` pour la mettre en pause, `filtre: false` pour l'exempter du filtre éditorial. Le premier passage d'une nouvelle source mémorise ses articles sans envoyer d'alerte. Les mots exclus se modifient dans `config/exclusions.yaml`.

### Lire l'état de la collecte

Sur la branche `data` : `articles/AAAA-MM-JJ.jsonl` (articles du jour), `state/sources.json` (dernière lecture et erreurs de chaque source), `sante/AAAA-MM.jsonl` (avertissements et erreurs), `state/alertes_en_attente.json` (alertes de nuit ou non envoyées).

## Le socle (`veille/`)

| Module | Rôle |
|---|---|
| `http` | Client commun : délai minimal par hôte, nouveaux essais avec attente croissante (429/5xx, `Retry-After`), en-têtes de navigateur, URL encodées (accents), repli SSL explicite |
| `telegram` | Un seul bot, en-têtes 🔔 🌅 🌆 📈 🏦 ⚠️, découpage à 4 096 caractères sur frontière de paragraphe sans casser une balise, repli en texte brut |
| `ia` | Gemini (modèles découverts dynamiquement, repli, pauses croissantes) puis Claude **en secours seulement**, plafond mensuel (`CLAUDE_PLAFOND_USD_MOIS`, 5 $ par défaut) et compteur tenu sur `data` ; sortie JSON validée par schéma |
| `etat` | État sur la branche `data` : chaque écriture est une transaction (resynchronisation, modification sur le contenu frais, poussée ; reprise si une autre tâche a écrit entre-temps) |
| `journal` | Journal console et événements structurés ; toute valeur de secret enregistrée est masquée |
| `config` | Chargement et validation de `config/*.yaml` |

## Branches

- `main` : code, configuration, workflows. **Aucune donnée.**
- `data` : état (`state/`), articles du jour, éditions, journal de santé (`sante/`). Écrite uniquement par les workflows, jamais à la main.

## Configuration

- `config/parametres.yaml` : modèle et tarifs de secours Claude, plafond, pauses Gemini, essais HTTP, plage silencieuse des alertes.
- `config/sources.yaml` : liste des sources (remplie au lot V1). Pour ajouter une source : une entrée avec `id`, `nom`, `url`, `type`, `chapitre`, `langue`, `alerte`, `payant`, `actif`.
- `config/exclusions.yaml` : mots exclus (lot V1).
- `config/jours_feries.yaml` : jours sans séance à la Bourse de Tunis (aucun point 📈). Fêtes à date fixe seulement : les fêtes religieuses mobiles sont à ajouter chaque année.
- `config/parametres.yaml` (`marches.mizeniti_url`) : adresse du Worker `marche-lecture` de Mizeniti, lu en lecture seule.

## Secrets du dépôt

`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `TG_TOKEN_VEILLE`, `TG_CHAT_ID` (posés par le porteur). Variable facultative : `CLAUDE_PLAFOND_USD_MOIS` (Settings → Variables). Aucun secret, e-mail ni identifiant personnel dans le dépôt (contrôlé par `tests/test_depot.py`).

## Développer en local

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt   # Windows
.venv/Scripts/python -m ruff check . && .venv/Scripts/python -m pytest
```

Les tests n'ont pas le droit d'ouvrir une connexion réseau (garde-fou dans `tests/conftest.py`).
