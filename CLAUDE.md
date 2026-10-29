# CLAUDE.md

## Projet
Arbre parrains/fillots de Centrale Lille. Voir README.md pour l'architecture.
Décisions, état et prochaines étapes : `C:\Users\matth\Documents\Vault\Perso\02-Projets\arbre-genealogique-cl\synthese.md`.
Manuel BDE (Claude Docs, hors dépôt car il contient un numéro de téléphone) : https://claude.ai/artifact/9iXnHLUjjyNGWbait7w4o5

## État (2026-10-29)
- Checklist avant partage presque finie : voir « Points ouverts » de la synthèse. Passation BDE : https://claude.ai/artifact/8PEd4Uzs9ASs1EjP1L8iQA

## Conventions
- Code, commentaires et données en français.
- `promo` = année d'entrée + 3 (jamais « annee_sortie »).
- Une personne n'a qu'un parrain ; un parrain peut avoir 1 à 3 fillots (ou plus, à signaler).
- Un écart de promo parrain/fillot ≠ 1 est une exception (ex. redoublement de Jasper Van Gossum, promo 2025) :
  à signaler, pas à bloquer. Un redoublant garde sa promo d'intégration et a la case `redoublant` cochée dans Personnes : son écart de 2 ans n'est alors plus signalé.
- Maillons manquants : personne de prénom « ? » (nom « Inconnu ») dans la promo concernée ; exportée avec `inconnu: true`.
- Grist : tables `Personnes` (prenom, nom, promo → Promos, parrain → Personnes, redoublant, + formules libelle et cle) et `Promos` (promo entier, nom).
- Pipeline en bibliothèque standard uniquement (pas de dépendance à installer en CI) ; d3 copié dans `site/vendor/`.
- Le site lit uniquement `site/data/arbre.json` : changer d'outil de saisie = réécrire un lecteur dans `pipeline/sources.py`.
- Tout ce qui finit dans le JSON du site est public : n'y mettre que prénom, nom, promo, sauf consentement.
- Les mainteneurs (BDE) ne codent pas forcément : les procédures doivent rester faisables sans terminal.

## Environnement
- `.venv` créé depuis `C:\Users\matth\miniconda3\envs\alertes-etf\python.exe` ; dépendances dans `requirements.txt`.
- Lancer Python avec `PYTHONIOENCODING=utf-8` dans le terminal Windows pour les accents.
- `outils/installer_import_rentree.py` est relançable : il répare/met à jour les formules Grist sans toucher aux données (identifiants de colonnes détachés des libellés).
