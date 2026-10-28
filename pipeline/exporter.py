"""Exporte les données validées vers le JSON lu par le site.

Usage :
    python -m pipeline.exporter --source grist   # production (GRIST_DOC_ID, GRIST_API_KEY)
    python -m pipeline.exporter --source csv     # local, depuis data/grist_import/

Code de sortie 1 si la validation trouve des erreurs : rien n'est écrit.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from pipeline import sources
from pipeline.validation import est_inconnu, valider

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "site" / "data" / "arbre.json"


def construire_json(promos, personnes):
    return {
        "genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "promos": {str(p["promo"]): p["nom"] for p in sorted(promos, key=lambda p: p["promo"])},
        "personnes": [
            {
                "id": p["id"],
                "prenom": p["prenom"],
                "nom": p["nom"],
                "promo": p["promo"],
                "parrain": p["parrain"],
                **({"inconnu": True} if est_inconnu(p) else {}),
            }
            for p in sorted(personnes, key=lambda p: p["id"])
        ],
    }


def rapport_markdown(personnes, erreurs, avertissements):
    lignes = [f"## Validation : {len(personnes)} personnes", ""]
    lignes.append(f"**{len(erreurs)} erreur(s)** (bloquantes), **{len(avertissements)} avertissement(s)**")
    for titre, items in (("Erreurs", erreurs), ("Avertissements", avertissements)):
        if items:
            lignes += ["", f"### {titre}", ""] + [f"- {x}" for x in items]
    return "\n".join(lignes) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["grist", "csv"], default="grist")
    parser.add_argument("--sortie", type=Path, default=SORTIE)
    args = parser.parse_args()

    try:
        promos, personnes = sources.lire_grist() if args.source == "grist" else sources.lire_csv()
    except sources.ErreurGrist as e:
        print(f"ERREUR : {e}", file=sys.stderr)
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
                f.write(f"## Export impossible\n\n{e}\n")
        sys.exit(1)
    erreurs, avertissements = valider(promos, personnes)

    rapport = rapport_markdown(personnes, erreurs, avertissements)
    print(rapport)
    if os.environ.get("GITHUB_STEP_SUMMARY"):  # affiché sur la page du run GitHub Actions
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(rapport)

    if erreurs:
        print("Publication annulée : corrige les erreurs dans Grist.", file=sys.stderr)
        sys.exit(1)

    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    donnees = construire_json(promos, personnes)
    # Données identiques à l'export précédent : on ne touche pas au fichier, pour que
    # la date affichée reste celle du dernier vrai changement (et éviter un commit vide).
    if args.sortie.exists():
        ancien = json.loads(args.sortie.read_text(encoding="utf-8"))
        if ancien.get("promos") == donnees["promos"] and ancien.get("personnes") == donnees["personnes"]:
            print("Aucun changement depuis le dernier export.")
            return
    # Une personne par ligne : l'historique git montre clairement qui a changé.
    compact = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
    texte = (
        f'{{"genere_le":{compact(donnees["genere_le"])},\n"promos":{compact(donnees["promos"])},\n"personnes":[\n'
        + ",\n".join(compact(p) for p in donnees["personnes"])
        + "\n]}\n"
    )
    args.sortie.write_text(texte, encoding="utf-8")
    print(f"Écrit : {args.sortie}")


if __name__ == "__main__":
    main()
