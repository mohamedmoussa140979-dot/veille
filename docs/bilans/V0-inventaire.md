# Inventaire — V0 socle — 14/11/2026

Anciens dépôts clonés en lecture seule dans `C:\Users\Admin\veille-anciens\` (aucune modification).

## Ce que le socle reprend des anciens scripts

| Ancien code | Ce qu'on en garde | Ce qu'on change |
|---|---|---|
| `sitemoussam/digest.py` · `modeles_disponibles`, `gemini` | Découverte des modèles par `ListModels` (méthode `generateContent`), exclusion des variantes image/audio/etc., modèles « lite » en dernier repli, tours successifs avec attente | Plus de noms de modèles écrits en dur (la liste de `digest.py` était périmée) ; classement par version décroissante, préversions en dernier ; clé envoyée dans un en-tête et non dans l'URL (sinon elle finit dans les journaux) ; pauses croissantes configurables au lieu de 4 × 60 s fixes |
| `sitemoussam/digest.py` · `telegram` | Repli en texte brut si l'envoi en HTML échoue | Découpage sur frontières de paragraphe avec fermeture/réouverture des balises (le message de `digest.py` était coupé au milieu d'une balise) ; un seul bot ; en-têtes par type |
| `sitemoussam/monitor.py` · `HEADERS`, `fetch` | En-têtes de navigateur ; repli sans vérification du certificat quand un site tunisien a un certificat invalide | Repli SSL explicite et journalisé (`ssl_repli=True`, désactivé par défaut) ; nouveaux essais avec attente croissante ; délai minimal par hôte |
| `veille-bfi/brief.py` | (lecteurs RSS, repris au lot V1) | — |
| `veille-awb/veille_awb.py` | (`resoudre_lien`, traduction : lots V1 et V4) | — |

Rien de `budgetpilot_alerts.py`, `principe.py`, ntfy.

## Hypothèses de la spec à vérifier pour V0

| # | Hypothèse | Comment on la vérifie | Résultat |
|---|---|---|---|
| H1 | La clé Gemini liste des modèles `generateContent` depuis un runner GitHub | Workflow `smoke` | **Confirmée** : 12 modèles retenus ; les trois plus récents répondaient 503, le 4e a répondu |
| H2 | Le jeton du workflow peut créer et pousser la branche `data` (paramètre « workflows en écriture ») | Workflow `smoke` | **Confirmée** : branche créée, état écrit puis relu, journal écrit |
| H3 | Telegram accepte nos messages HTML découpés | Workflow `smoke` + réception sur le téléphone | **Confirmée côté API** après « Démarrer » du porteur : message court et message long en 4 parties acceptés, sans repli texte brut (1re exécution : « chat not found », bot non démarré). Rendu sur téléphone à confirmer |
| H4 | La clé Anthropic est valide ; la forme de la requête de secours est acceptée | `GET /v1/models` + un appel minimal | **Confirmée** : HTTP 200 ; appel accepté (`output_config.effort`, `anthropic-version: 2023-06-01`) ; coût mesuré 0,000086 $ |
| H5 | Python 3.12 et le cache pip sont disponibles sur le runner | Workflow `tests` | **Confirmée** : ruff, ruff format et pytest verts sur runner Ubuntu |

Les secrets ne sont jamais lus ni affichés : seuls les workflows les utilisent, et le journal masque toute valeur de secret enregistrée.

## Décisions d'implémentation (sans effet sur une décision V1–V42)

- **Fuseau** : décalage fixe UTC+1 (la Tunisie n'a plus d'heure d'été) plutôt que `zoneinfo`, qui exige le paquet `tzdata` sous Windows.
- **État sur `data`** : dépôt Git en clone superficiel ; chaque écriture est une *transaction* (resynchronisation, application de la modification sur le contenu frais, commit, poussée ; en cas de refus, on recommence sur le contenu frais). Aucune écriture concurrente perdue (critère A9), testé avec de vrais dépôts Git locaux.
- **Identité des commits du bot** : adresse `noreply` ; aucune adresse personnelle dans l'historique public.
- **Fins de ligne** : `.gitattributes` impose LF (l'avertissement CRLF est apparu au premier commit des documents).
- **Modèle de secours** : `claude-sonnet-5-5` par défaut (paramètre), 2 $ / 10 $ par million de tokens ; coût calculé depuis le champ `usage` de la réponse ; refus préventif si la dépense du mois + la borne haute de l'appel dépasserait le plafond.
