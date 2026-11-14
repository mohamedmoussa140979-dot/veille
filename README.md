# veille

Veille économique consolidée (Tunisie, Afrique, international) : alertes immédiates, deux synthèses par jour, points marchés, veille AWB. Dépôt public, exécuté par GitHub Actions.

Tout est décrit dans `docs/` : règles du chantier (`00-regles-chantier.md`), spécification (`spec-veille.md`), décisions du porteur (`journal-decisions.md`). L'avancement est dans `docs/bilans/ETAT.md`, un bilan par lot dans `docs/bilans/`.

## État

Lot V0 (socle) livré (voir `docs/bilans/V0-bilan.md`). Lot V1 (collecte et alertes) en cours. Les workflows de collecte, de synthèse, de marchés, d'AWB et de santé arrivent avec les lots V1 à V5.

## Ce que fait chaque workflow

| Workflow | Déclenchement | Rôle |
|---|---|---|
| `tests` | à chaque `push` (hors branche `data`) | `ruff` + `pytest`, sans réseau |
| `smoke` | manuel (`Actions` → `smoke` → *Run workflow*) | Essai réel : branche `data`, Gemini, Claude, Telegram. Case « tester_claude » : un appel Claude minimal (quelques millièmes de dollar) |

Relancer un essai depuis un terminal :

```bash
gh workflow run smoke.yml -R mohamedmoussa140979-dot/veille
gh workflow run smoke.yml -R mohamedmoussa140979-dot/veille -f tester_claude=true
```

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

## Secrets du dépôt

`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `TG_TOKEN_VEILLE`, `TG_CHAT_ID` (posés par le porteur). Variable facultative : `CLAUDE_PLAFOND_USD_MOIS` (Settings → Variables). Aucun secret, e-mail ni identifiant personnel dans le dépôt (contrôlé par `tests/test_depot.py`).

## Développer en local

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt   # Windows
.venv/Scripts/python -m ruff check . && .venv/Scripts/python -m pytest
```

Les tests n'ont pas le droit d'ouvrir une connexion réseau (garde-fou dans `tests/conftest.py`).
