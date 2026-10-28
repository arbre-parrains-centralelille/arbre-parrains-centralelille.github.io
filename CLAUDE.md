# CLAUDE.md

## Projet
Arbre parrains/fillots de Centrale Lille. Voir README.md pour l'architecture.

## Conventions
- Code, commentaires et données en français.
- `promo` = année d'entrée + 3 (jamais « annee_sortie »).
- Une personne n'a qu'un parrain ; un parrain peut avoir 1 à 3 fillots (ou plus, à signaler).
- Un écart de promo parrain/fillot ≠ 1 est une exception (ex. redoublement de Jasper Van Gossum, promo 2025) :
  à signaler, pas à bloquer.
- Maillons manquants : personne « ? Inconnu » dans la promo concernée.
- Tout ce qui finit dans le JSON du site est public : n'y mettre que prénom, nom, promo, sauf consentement.
- Les mainteneurs (BDE) ne codent pas forcément : les procédures doivent rester faisables sans terminal.

## Environnement
- `.venv` créé depuis `C:\Users\matth\miniconda3\envs\alertes-etf\python.exe` ; dépendances dans `requirements.txt`.
- Lancer Python avec `PYTHONIOENCODING=utf-8` dans le terminal Windows pour les accents.
