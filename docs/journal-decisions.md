# Journal des décisions — chantier veille (14/11/2026)

Décisions du porteur prises pendant le cadrage du 14/11/2026. Elles priment sur toute hypothèse des specs.

## Diagnostic et facturation
- V1. Cause de la panne : compte GitHub `abtmohamedmoussa-svg` verrouillé depuis le 10/10/2026 (autorisation de carte refusée après un dépassement de 0,98 $ du quota Actions, causé par `pfm-platform`). Ticket ouvert auprès du support GitHub par le porteur.
- V2. BudgetPilot Alerts abandonné ; workflow désactivé le 14/11.
- V3. E-mail retiré de `veille-awb/.github/workflows/veille.yml` (secret `MYMEMORY_MAIL`) le 14/11 ; il reste dans l'historique Git public.
- V4. Hébergement : dépôt public sur GitHub Actions (gratuit), sous un **compte machine** dédié `mohamedmoussa140979-dot` (budget Actions 0 $, aucun moyen de paiement). Pas de Cloudflare pour la veille elle-même.
- V5. Dépôt créé le 14/11 : `mohamedmoussa140979-dot/veille` (public, README, workflows en écriture, Pages en source « GitHub Actions », `abtmohamedmoussa-svg` invité comme collaborateur).
- V6. Secrets posés par le porteur : `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `TG_CHAT_ID`, `TG_TOKEN_VEILLE`.

## Périmètre
- V7. Principe du jour abandonné.
- V8. Un seul bot Telegram pour tous les flux, avec en-têtes 🔔 🌅 🌆 📈 🏦 ⚠️.
- V9. Alertes immédiates : Telegram uniquement, pour le porteur seul ; plage silencieuse 22:00–07:00 (envoi groupé à 07:00).
- V10. Push Mizeniti écarté pour l'instant (à revoir plus tard, pas certain).
- V11. ntfy abandonné.
- V12. Archives HTML sur GitHub Pages depuis le dépôt `veille`.
- V13. Veille AWB conservée, hors Mizeniti.
- V14. Points marchés conservés (Telegram).

## Horaires (heures de Tunis)
- V15. Collectes : 07:15, 09:15, 11:15, 13:15, 15:15, 17:15, 20:15 en semaine ; 09:15 et 18:15 le week-end.
- V16. Synthèses : 07:30 et 18:30 en semaine ; 09:30 le week-end.
- V17. Marchés : 11:00 (mi-séance), 14:45 (clôture BVMT, horaire à vérifier), 22:45 (clôture internationale), jours ouvrés. **Modifiée par V42** : plus de mi-séance, clôture Bourse à 17:20.
- V18. AWB : 08:30 et 18:30. Santé : 21:00, message du dimanche même sans anomalie.
- V19. Phase 2 : horaires pilotés depuis le back-office de Mizeniti, déclenchement par une tâche planifiée Cloudflare existante (pas de tâche toutes les heures sur GitHub).

## Ligne éditoriale et chapitres
- V20. Économie et technologie seulement ; exclus : sport, arts, guerres, politique, faits divers, catastrophes, people.
- V21. Politique à impact économique : gardée, et peut être l'actualité principale.
- V22. Chapitres, dans l'ordre : L'essentiel ; Économie tunisienne ; Bourse, entreprises et acteurs économiques ; Économie et marchés internationaux ; Économie africaine ; Technologie.
- V23. Économie tunisienne : réglementation, notations, publications INS et finances publiques, revue de presse (y compris banques non cotées).
- V24. Chapitre 3 couvre tout acteur économique, coté ou non.
- V25. Ligne « Impact ménage » sous les sujets du chapitre 2 qui s'y prêtent.
- V26. Tableaux fixes des chapitres 3 et 4 validés, chaque ligne avec lien vers sa source (notamment fiche BVMT au chapitre 3).
- V27. Synthèse en français uniquement ; articles arabes pris en compte et cités.

## Sources
- V28. Liste existante validée ; corriger BCT et INS ; vérifier CMF et BVMT (fonctionnent) ; Macsa et Tunisie Valeurs retirés.
- V29. Ajout de sources sans code : depuis le back-office Mizeniti (phase 2).

## IA
- V30. Gemini (gratuit) en principal ; Claude en **secours uniquement** si Gemini est indisponible ; plafond par défaut 5 $/mois, modifiable.

## Mizeniti — Actualités
- V31. Rubrique « Actualités », entrée du menu Plus avant ou après « Marché ».
- V32. Carte « L'essentiel du matin » sur l'Accueil.
- V33. Quatre chiffres : TUNINDEX, EUR/TND (BCT), Brent, TMM.
- V34. Mise à jour deux fois par jour ; archives 12 mois ; recherche par mot-clé, date, source.
- V35. Réservé aux licences actives ; rubrique entièrement absente sans licence.
- V36. Pas de maquette préalable ; respect des règles communes du 13/11 (gabarit G4).
- V37. Liens : ouverture par-dessus l'app, liens Google News résolus, paramètres de suivi retirés, pastilles 🔒 et langue, « déjà lu », hors connexion grisé, appui long copier/partager.
- V38. Pas de vérification automatique des liens morts.
- V39. Spec et prompt rédigés après clôture complète du cadrage (demande du porteur).
- V40. Retrait de l'existant : archivage puis suppression des quatre anciens dépôts par le porteur, après une semaine de fonctionnement.
- V41. **Traduction** : lien « Lire en français » (traduction automatique Google de la page d'origine) pour les articles en anglais et en arabe non payants, dans Mizeniti (bouton « FR ») et sur Telegram (« (FR) »). Pas de traduction intégrale faite par nous.

## Bourse (14/11, 21:09)
- V42. **irbe7 abandonné** pour les données de Bourse. Source principale : données déjà publiées par Mizeniti (routes `/marche/bourse/*` du Worker `marche-lecture`) ; repli : site de la Bourse directement (`market_resume.ndjson`, bulletin officiel), seulement s'il répond aux runners GitHub. Aucun rediffuseur. Conséquence : point de mi-séance de 11:00 supprimé faute de source publique en séance (V17 modifiée) ; point de clôture déplacé de 14:45 à 17:20.
