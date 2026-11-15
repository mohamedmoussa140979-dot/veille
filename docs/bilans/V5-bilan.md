# Bilan — V5 santé et bascule — 15/11/2026

## En une phrase
Le contrôle de santé de 21:00 tourne et a détecté, sur un vrai runner, la seule anomalie réelle de la soirée ; le README d'exploitation est complet. Le bilan de la première semaine et le rappel d'archivage des quatre anciens dépôts ne peuvent venir qu'après sept jours de fonctionnement réel : ils sont planifiés dans `ETAT.md`.

## Fait
- **Contrôle quotidien (21:00 Tunis)** : source sans nouvel article au-delà de son délai (presse 3 jours ouvrés, INS 10 jours, BCT, CMF et BVMT 7 jours) ou illisible depuis six passages ; workflow planifié en échec dans les dernières 24 h ou qui n'a pas réussi depuis plus que son silence normal (collecte 16 h, édition 25 h, marchés 70 h, AWB 16 h) ; édition du jour manquante (matin et soir en semaine, matin le week-end) ; Gemini en échec avec Claude utilisé ; plafond Claude à 80 % ou atteint ; Yahoo sans donnée ; traduction AWB sans donnée ; données de Bourse de Mizeniti plus anciennes que le dernier jour ouvré.
- **Message ⚠️ groupé** : une ligne par anomalie avec l'action suggérée. **Dimanche** : « ✅ Semaine complète » (éditions et alertes de la semaine) sans anomalie ; sinon un seul message ⚠️ qui reprend ces chiffres.
- **Compteur d'alertes par jour** (`state/alertes_stats.json`), tenu par la collecte, pour le message du dimanche.
- **Journal de santé** : chaque passage écrit un événement `sante_controle` sur `data`.
- **README final** : rôle de chaque workflow, relance d'un essai, ajout d'une source, lecture de l'état, que faire en cas de panne, bascule.

## Vérifié, et comment
| Critère | Contrôle | Résultat |
|---|---|---|
| A8 — une source simulée muette au-delà de son délai apparaît au rapport de santé | `tests/test_sante.py` : presse (3 jours ouvrés), INS (10 jours), BCT, CMF, BVMT (7 jours), juste avant et juste après la limite, source inactive ou jamais observée ignorée, source illisible | Vert |
| Chaque contrôle du § 10 | 21 tests : tâches en échec ou arrêtées (échec ancien ignoré, essai manuel ignoré), éditions manquantes, secours Claude, plafond à 80 % et atteint, Yahoo, traduction, Bourse périmée, jour ouvré (week-end, jour férié) | Vert |
| Message ⚠️ et message du dimanche | Tests de passage complet : rien en semaine quand tout va bien ; message groupé avec action pour une source muette ; dimanche sans anomalie ; dimanche avec anomalie ; Telegram en panne (code de sortie non nul, événement journalisé) | Vert |
| Essai réel (exécution 43656539713, dimanche simulé) | L'API GitHub répond avec le jeton du workflow (permission `actions: read`) ; une anomalie détectée : le premier essai d'édition raté de la soirée (corrigé depuis) ; semaine : 1 édition, 0 alerte | Vert |
| CI | `ruff`, 278 tests, CI verte | Vert |

## Essai réel (workflow, journal, résultat constaté)
- Le message ⚠️ a été envoyé (« Le workflow « edition » a échoué (15/11 00:16) » avec le lien du journal et la phrase de la semaine). Cet échec était un essai déclenché à la main : le contrôle ne compte désormais que les échecs de tâches **planifiées**, comme la spec.
- Aucune autre anomalie : sources récentes, éditions présentes, Bourse à jour, plafond Claude à 0,000086 $.

## Non vérifié
- **Premier contrôle planifié de 21:00** et premier **vrai message du dimanche** (dimanche 15/11 à 21:00 : à constater sur le téléphone).
- **Une vraie panne** : on ne peut pas provoquer, sans risque, une source réellement muette ; A8 est vérifié par simulation.
- **Silences normaux des workflows** : calculés sur le calendrier de la spec ; à ajuster si GitHub retarde souvent ses crons (un faux positif se verra dès les premiers jours).
- **Une panne complète du compte GitHub** ne peut pas se signaler elle-même (voir README).
- **Fêtes religieuses mobiles** absentes de `config/jours_feries.yaml`.

## Écarts à la spec
- Aucun. (Le message du dimanche « ✅ Semaine complète » est un en-tête ajouté aux six du § 8.1, comme le prévoit le § 10.)

## Choix faits sans le porteur
- « Jours ouvrés » : lundi-vendredi, jours fériés non retranchés ; un jour férié rapproche donc l'alerte (jamais l'inverse).
- Seuls les échecs de workflows **planifiés** déclenchent une alerte ; une exécution manuelle ratée n'en déclenche pas.
- Le dimanche avec anomalie : un seul message (⚠️ + chiffres de la semaine), pas deux.

## À regarder sur le téléphone (cinq points au plus)
1. Le message « ⚠️ Santé » reçu vers 00:07 : une anomalie, une action, la ligne « Cette semaine : 1 édition, 0 alerte ».
2. Dimanche vers 21:00 : « ✅ Semaine complète » (ou un ⚠️ lisible) ; lundi à 21:00 : rien si tout va bien.
3. Les phrases sont-elles claires, et les actions suggérées utiles ?
4. Aucun faux positif répété dans les trois premiers jours (sinon me le dire pour ajuster les seuils).
5. Dans une semaine : demander le bilan de la première semaine (voir `ETAT.md`).

## Suite
Bilan de la première semaine après sept jours de fonctionnement réel, puis archivage des quatre anciens dépôts par le porteur.
