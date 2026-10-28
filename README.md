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

## Organisation du dépôt

| Dossier | Rôle |
|---|---|
| `migration/` | Migration unique de l'ancien Google Sheet vers `data/grist_import/` (CSV à importer dans Grist) |
| `pipeline/` | `sources.py` lit Grist (ou les CSV locaux), `validation.py` vérifie les règles, `exporter.py` écrit `site/data/arbre.json` |
| `site/` | Site statique : `index.html`, `style.css`, `app.js`, d3 dans `vendor/`, données dans `data/` |
| `tests/` | Tests de la validation (`python -m unittest`) |
| `.github/workflows/publier.yml` | Chaque nuit / à la demande : export Grist → validation → archive git → GitHub Pages |

## Commandes utiles

```
python -m unittest                          # tests
python -m pipeline.exporter --source csv    # export depuis data/grist_import/ (sans Grist)
python -m pipeline.exporter --source grist  # export depuis Grist (variables dans .env, voir .env.example)
python -m http.server 8765 -d site          # voir le site sur http://localhost:8765
python migration/migrer_gsheet.py           # rejouer la migration de l'ancien sheet
```

## Configuration GitHub

- **Settings → Pages → Source : GitHub Actions**
- **Settings → Secrets and variables → Actions** :
  variable `GRIST_DOC_ID` (et `GRIST_SERVEUR` si ce n'est pas `https://docs.getgrist.com`),
  secret `GRIST_API_KEY`. Sans `GRIST_DOC_ID`, l'Action publie le JSON déjà présent dans le dépôt.

## Données personnelles

Seuls prénom, nom et promo sont publiés. Toute demande de retrait passe par le contact du site.
