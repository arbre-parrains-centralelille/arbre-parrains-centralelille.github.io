# Arbre généalogique Centrale Lille — parrains / fillots

Plateforme publique pour consulter les lignées parrain → fillot des étudiants de Centrale Lille :
on cherche un étudiant, on voit sa famille (ancêtres, frères et sœurs, descendants).

## Architecture

```
[Grist : saisie par le BDE]  →  [GitHub Action + Python : export, validation, JSON]  →  [Site statique (GitHub Pages)]
```

- **Grist** est la source de vérité (tables `Promos` et `Personnes`, le parrain est une référence).
- Le **site ne lit jamais Grist directement** : il lit un JSON validé, produit par le script Python.
- **Promo** = année d'entrée + 3 (année de diplôme supposée). Ex. : entrée en sept. 2023 → promo 2026.

## État actuel

- `migration/migrer_gsheet.py` : migration unique de l'ancien Google Sheet vers `data/grist_import/`
  (`promos.csv`, `personnes.csv`, `rapport_migration.txt`).
- À venir : pipeline d'export/validation, site, manuel pour le BDE.

## Lancer la migration

```
python migration/migrer_gsheet.py              # depuis data/source/gsheet_arbre.csv
python migration/migrer_gsheet.py --telecharger  # re-télécharge le sheet d'abord
```

## Données personnelles

Seuls prénom, nom et promo sont publiés. Toute demande de retrait passe par le contact du site.
