# Inventaire — V3 marchés — 15/11/2026

## Hypothèses de la spec vérifiées
| # | Hypothèse | Constat |
|---|---|---|
| M1 | Le Worker `marche-lecture` de Mizeniti est lisible anonymement | **Confirmé.** Adresse : `https://marche-lecture.mizeniti2026-9b1.workers.dev` (valeur par défaut de `EXPO_PUBLIC_MARCHE_URL` dans les scripts de déploiement de Mizeniti ; elle n'est ni dans le README ni dans `wrangler.toml` de `marche-jobs`). Routes testées en GET anonyme : `/marche/etat.json`, `/marche/bourse/index.json`, `indices.json`, `volumes.json`, `capitalisation.json`, `/marche/taux/{tmm,tre,change,inflation}.json` : HTTP 200 |
| M2 | Mêmes chiffres que l'application, aucune collecte en double | Oui : TUNINDEX 18 989,99 au 13/11/2026 (stocké en centièmes : 1898999), variation du jour +0,79 % |
| M3 | Un runner GitHub accède directement au site de la Bourse | **Non testé et inutile** : le repli direct n'est pas construit (voir « Choix »). Le site de la Bourse répond depuis un poste personnel |
| M4 | Indice sectoriel Banques dans `indices.json` | Oui : code `8300`. TUNINDEX20 et les sectoriels ont `variation_jour` à `null` (fréquence « MENSUEL », un point par bulletin) : la variation du jour est calculée depuis `precedente` quand le point précédent est publié |
| M5 | Yahoo répond pour les instruments du chapitre 4 | Oui pour Brent (`BZ=F`), gaz naturel (`NG=F`), or (`GC=F`), blé (`ZW=F`), S&P 500, Euro Stoxx 50, CAC 40, EUR/USD. **Non pour le MASI** (aucun symbole ; la recherche Yahoo ne le connaît pas) |
| M6 | Cours BCT EUR/TND et USD/TND, TMM | Servis par Mizeniti (`/marche/taux/change.json`, `tmm.json`, source BCT) : EUR 3,3639 et USD 3,0335 au 12/11/2026, TMM 7,0 % (octobre 2026) |
| M7 | Fiche BVMT de chaque valeur (lien du tableau du chapitre 3) | **Introuvable** : aucune adresse de fiche par valeur sur le site de la Bourse (essais : /valeur/…, /fiche-valeur/…, /cotation, pages d'émetteurs) |

## Décisions d'implémentation (sans effet sur V1–V42)
- **Source unique pour la Bourse et la BCT : Mizeniti**, en lecture HTTP seule (V42). Aucun repli sur le site de la Bourse (accès non vérifiable depuis GitHub, risque connu en octobre) ni sur la page BCT : source muette = tiret explicite.
- Unités : indices en centièmes de point, cours en millimes (÷ 100 et ÷ 1000), capitaux en millimes.
- `jours_feries.yaml` : jours sans séance connus à date fixe ; les fêtes religieuses mobiles sont à compléter chaque année (en leur absence, le point de 18:20 annonce « séance non encore publiée »).
- Le tableau du chapitre 3 et celui du chapitre 4 sont des objets `tableau` du contrat v1 ; le chapitre apparaît dès qu'il a un tableau, même sans sujet (le contrat v1 est assoupli : `sujets` peut être vide si `tableau` est présent).
