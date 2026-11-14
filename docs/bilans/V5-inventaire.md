# Inventaire — V5 santé et bascule — 15/11/2026

## Ce que V5 s'appuie sur (déjà en place)
| Besoin du § 10 | Donnée disponible | Origine |
|---|---|---|
| Source sans aucun article depuis N jours | `state/sources.json` : `dernier_nouvel_article`, `premier_passage`, `erreurs_consecutives`, `derniere_erreur` par source | V1 |
| Tâche non exécutée ou en échec dans les 24 h | API GitHub `GET /repos/{dépôt}/actions/runs` avec le jeton du workflow (permission `actions: read`) | à vérifier à l'essai réel |
| Édition manquante | liste de `editions/` sur `data` | V2 |
| Gemini en échec, Claude utilisé ; plafond à 80 % | événements `claude_secours_utilise`, `claude_plafond_atteint` dans `sante/` ; `state/claude.json` | V0, V2 |
| Yahoo, traduction AWB sans donnée | événements `yahoo_echec`, `yahoo_sans_donnee`, `awb_traduction_sans_donnee` | V3, V4 |
| Données de Bourse de Mizeniti périmées | date du TUNINDEX dans `/marche/bourse/indices.json` comparée au dernier jour ouvré (week-end et jours fériés exclus) | V3 |
| Message du dimanche (éditions et alertes de la semaine) | `editions/` ; compteur `state/alertes_stats.json` (nouveau, tenu par la collecte) | V1, V5 |

## Hypothèses à vérifier
| # | Hypothèse | Constat |
|---|---|---|
| S1 | Le jeton du workflow peut lister les exécutions du dépôt | **À vérifier à l'essai réel** (workflow `sante`, permission `actions: read`) |
| S2 | Les silences normaux de chaque workflow | Calculés sur le calendrier de la spec § 5 : collecte 15 h (week-end), édition 22 h (dimanche → lundi), marches 66 h (vendredi 22:45 → lundi 17:20), AWB 14 h ; seuils = silence normal + marge |

## Décisions d'implémentation (sans effet sur V1–V42)
- « Jours ouvrés » de la presse : lundi à vendredi, jours fériés non retranchés (un jour férié rapproche un peu l'alerte, jamais l'inverse).
- Un message ⚠️ groupé, une ligne par anomalie avec l'action suggérée ; le dimanche : « ✅ Semaine complète » sans anomalie, sinon un seul message ⚠️ qui reprend la phrase de la semaine.
- Pas de repli direct sur le site de la Bourse (V3) : la donnée périmée est simplement signalée.
- Le bilan de la première semaine et le rappel d'archivage des anciens dépôts ne peuvent pas être produits avant sept jours de fonctionnement réel (voir `ETAT.md`).
