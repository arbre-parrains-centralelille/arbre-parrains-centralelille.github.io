"""Migration unique : ancien Google Sheet (format « large ») -> tables normalisées pour Grist.

Ancien format : une ligne = un fillot + tous ses parrains, une paire de colonnes
(Prénom, Nom) par promo, de la plus récente à la plus ancienne.
Nouveau format : une ligne = une personne, avec une référence vers son parrain.

Usage :
    python migration/migrer_gsheet.py            # lit data/source/gsheet_arbre.csv
    python migration/migrer_gsheet.py --telecharger   # re-télécharge le sheet d'abord

Sorties (data/grist_import/) : promos.csv, personnes.csv, rapport_migration.txt
"""

import csv
import re
import sys
import unicodedata
import urllib.request
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SOURCE = RACINE / "data" / "source" / "gsheet_arbre.csv"
SORTIE = RACINE / "data" / "grist_import"
URL_SHEET = (
    "https://docs.google.com/spreadsheets/d/1d2sJz5xENNiKTg9E9DydZYuoyB03A9dROU2TigF8noM"
    "/gviz/tq?tqx=out:csv&sheet=Arbre%20G%C3%A9n%C3%A9alogique"
)

# Promo = année d'entrée à Centrale Lille + 3 (année de diplôme supposée).
DECALAGE_PROMO = 3

# --- Corrections validées avec Matthieu ----------------------------------------
# Les clés utilisent l'année d'entrée telle qu'écrite dans le sheet.

# Cellules dont le prénom et le nom sont inversés : (année d'entrée, prénom lu, nom lu)
INVERSIONS = {
    (2021, "Chauchat", "Guillaume"),
    (2021, "Jouan", "Hugo"),
}

# Cellules à réécrire : (année, prénom lu, nom lu) -> (prénom, nom)
REECRITURES = {
    (2020, "Thomas Guiho", ""): ("Thomas", "Guiho"),
    (2019, "Timothé", "Heard"): ("Timothée", "Heard"),       # même personne
    (2021, "Chabrand", "François"): ("Madeleine", "François"),  # faute de copie
}

# Personne apparaissant dans une autre colonne que sa promo d'intégration
# (redoublement) : (année lue, prénom, nom) -> année d'entrée réelle
REDOUBLEMENTS = {
    (2023, "Jasper", "Van Gossum"): 2022,
}

# Fillots ayant plusieurs parrains dans le sheet : (année, prénom, nom) -> parrain retenu
# None = garder le parrain qui a le plus d'ancêtres.
CONFLITS = {
    (2024, "Clément", "Burin"): None,
    (2024, "Mehdi", "Manssouri"): ("Salwa", "Azariouh"),
}


def nettoyer(texte):
    texte = re.sub(r"\s+", " ", texte).strip()
    return re.sub(r"-{2,}", "-", texte)


def cle_nom(prenom, nom):
    """Clé d'identité tolérante aux accents, à la casse et aux tirets."""
    s = unicodedata.normalize("NFKD", f"{prenom} {nom}").encode("ascii", "ignore").decode()
    return re.sub(r"[\s\-']+", " ", s).strip().lower()


def lire_sheet(chemin):
    lignes = list(csv.reader(chemin.open(encoding="utf-8")))
    entete, donnees = lignes[0], lignes[2:]
    promos = []  # (année d'entrée, nom de promo) par colonne
    for i in range(0, len(entete), 2):
        m = re.match(r"Promo (\d{4})\s*-\s*(.+)", entete[i].strip())
        promos.append((int(m.group(1)), m.group(2).strip()))
    return promos, donnees


def main():
    if "--telecharger" in sys.argv:
        SOURCE.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(URL_SHEET, SOURCE)

    promos, donnees = lire_sheet(SOURCE)
    rapport = []
    personnes = {}  # clé -> {"prenom", "nom", "entree"}
    parrains = defaultdict(set)  # clé fillot -> {clés parrains}
    utilisees = set()  # corrections effectivement appliquées

    def personne(entree, prenom, nom):
        cle_corr = (entree, prenom, nom)
        if cle_corr in INVERSIONS:
            prenom, nom = nom, prenom
            utilisees.add(("inv",) + cle_corr)
        if cle_corr in REECRITURES:
            prenom, nom = REECRITURES[cle_corr]
            utilisees.add(("reec",) + cle_corr)
        if cle_corr in REDOUBLEMENTS:
            entree = REDOUBLEMENTS[cle_corr]
            utilisees.add(("red",) + cle_corr)
        cle = (entree, cle_nom(prenom, nom))
        personnes.setdefault(cle, {"prenom": prenom, "nom": nom, "entree": entree, "inconnu": False})
        return cle

    for num, ligne in enumerate(donnees, start=3):
        ligne += [""] * (2 * len(promos) - len(ligne))
        chaine = []  # (indice de colonne, clé), du fillot vers les ancêtres
        for c, (entree, _) in enumerate(promos):
            prenom, nom = nettoyer(ligne[2 * c]), nettoyer(ligne[2 * c + 1])
            if prenom or nom:
                chaine.append((c, personne(entree, prenom, nom)))
        for (c1, fillot), (c2, parrain) in zip(chaine, chaine[1:]):
            # Promos manquantes entre deux personnes : on insère des « parrains inconnus ».
            # Ils sont identifiés par le fillot connu juste en dessous, pour que deux
            # lignes décrivant la même lignée partagent les mêmes inconnus.
            enfant = fillot
            for c in range(c1 + 1, c2):
                entree = promos[c][0]
                cle = (entree, f"?inconnu de {enfant[1]}")
                if cle not in personnes:
                    personnes[cle] = {"prenom": "?", "nom": "Inconnu", "entree": entree, "inconnu": True}
                    rapport.append(f"Parrain inconnu créé en promo {entree + DECALAGE_PROMO} (ligne {num})")
                parrains[enfant].add(cle)
                enfant = cle
            parrains[enfant].add(parrain)

    # --- Résolution des conflits (fillots avec plusieurs parrains) ---
    def nb_ancetres(cle, vus=()):
        ps = parrains.get(cle, set())
        return 0 if not ps or cle in vus else 1 + max(nb_ancetres(p, vus + (cle,)) for p in ps)

    erreurs = []
    for fillot, ps in list(parrains.items()):
        if len(ps) <= 1:
            continue
        p = personnes[fillot]
        regle = (p["entree"], p["prenom"], p["nom"])
        if regle not in CONFLITS:
            noms = [f"{personnes[x]['prenom']} {personnes[x]['nom']}" for x in ps]
            erreurs.append(f"Conflit non résolu : {p['prenom']} {p['nom']} -> {noms}")
            continue
        choix = CONFLITS[regle]
        if choix is None:
            retenu = max(ps, key=nb_ancetres)
            detail = ", ".join(
                f"{personnes[x]['prenom']} {personnes[x]['nom']} ({nb_ancetres(x)} ancêtres)" for x in ps
            )
        else:
            retenu = next(x for x in ps if x[1] == cle_nom(*choix))
            detail = "choix manuel"
        parrains[fillot] = {retenu}
        r = personnes[retenu]
        rapport.append(f"Conflit {p['prenom']} {p['nom']} : parrain retenu {r['prenom']} {r['nom']} [{detail}]")

    # --- Vérifications ---
    toutes = {("inv",) + k for k in INVERSIONS} | {("reec",) + k for k in REECRITURES} | {
        ("red",) + k for k in REDOUBLEMENTS
    }
    for k in sorted(toutes - utilisees):
        erreurs.append(f"Correction jamais appliquée (cellule introuvable) : {k}")

    libelles = {}
    for cle, p in personnes.items():
        promo = p["entree"] + DECALAGE_PROMO
        base = " ".join(x for x in (p["prenom"], p["nom"]) if x) + f" ({promo})"
        libelles[cle] = base
    doublons = [l for l in libelles.values() if list(libelles.values()).count(l) > 1]
    if doublons:
        # Les inconnus d'une même promo sont numérotés.
        compteur = defaultdict(int)
        for cle in sorted(libelles, key=lambda k: k[1]):
            if personnes[cle]["inconnu"] and libelles[cle] in doublons:
                compteur[libelles[cle]] += 1
                p = personnes[cle]
                p["nom"] = f"Inconnu {compteur[libelles[cle]]}"
                libelles[cle] = f"{p['prenom']} {p['nom']} ({p['entree'] + DECALAGE_PROMO})"
    vus = set()
    for l in libelles.values():
        if l in vus:
            erreurs.append(f"Libellé en double : {l}")
        vus.add(l)

    for fillot, ps in parrains.items():
        (parrain,) = ps
        ecart = personnes[parrain]["entree"] - personnes[fillot]["entree"]
        if ecart != -1:
            rapport.append(
                f"Écart de promo inhabituel ({-ecart} an(s)) : {libelles[parrain]} -> {libelles[fillot]}"
            )
    for cle, p in personnes.items():
        if not p["prenom"] or not p["nom"]:
            rapport.append(f"Nom incomplet : {libelles[cle]!r}")

    if erreurs:
        print("ERREURS :\n  " + "\n  ".join(erreurs))
        sys.exit(1)

    # --- Écriture ---
    SORTIE.mkdir(parents=True, exist_ok=True)
    with (SORTIE / "promos.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["promo", "nom"])
        for entree, nom in sorted(promos, reverse=True):
            w.writerow([entree + DECALAGE_PROMO, nom])

    ordre = sorted(personnes, key=lambda k: (-personnes[k]["entree"], cle_nom(personnes[k]["nom"], personnes[k]["prenom"])))
    with (SORTIE / "personnes.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["prenom", "nom", "promo", "parrain"])
        for cle in ordre:
            p = personnes[cle]
            parrain = next(iter(parrains[cle]), None)
            w.writerow([p["prenom"], p["nom"], p["entree"] + DECALAGE_PROMO, libelles[parrain] if parrain else ""])

    nb_liens = sum(1 for ps in parrains.values() if ps)
    resume = [
        f"{len(personnes)} personnes, {nb_liens} liens parrain -> fillot, {len(promos)} promos",
        "",
    ] + rapport
    (SORTIE / "rapport_migration.txt").write_text("\n".join(resume) + "\n", encoding="utf-8")
    print("\n".join(resume))


if __name__ == "__main__":
    main()
