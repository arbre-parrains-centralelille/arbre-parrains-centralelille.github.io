"""Règles de validation des données avant publication.

- Erreur : la publication est bloquée (le site garde la dernière version valide).
- Avertissement : publié quand même, mais signalé dans le rapport.
"""

import re
import unicodedata
from collections import defaultdict

MAX_FILLOTS = 3


def cle_nom(prenom, nom):
    s = unicodedata.normalize("NFKD", f"{prenom} {nom}").encode("ascii", "ignore").decode()
    return re.sub(r"[\s\-–—'’_]+", " ", s).strip().lower()


def est_inconnu(p):
    return p["prenom"] == "?"


def libelle(p):
    return " ".join(x for x in (p["prenom"], p["nom"]) if x) + f" ({p['promo']})" + f" [ligne {p['id']}]"


def valider(promos, personnes):
    erreurs, avertissements = [], []

    # --- Promos ---
    annees = {}
    for pr in promos:
        if not isinstance(pr["promo"], int):
            erreurs.append(f"Promo invalide (doit être une année entière) : {pr['promo']!r} [ligne {pr['id']}]")
        elif pr["promo"] in annees:
            erreurs.append(f"Promo en double : {pr['promo']}")
        else:
            annees[pr["promo"]] = pr["nom"]
        if not pr["nom"]:
            avertissements.append(f"Promo {pr['promo']} sans nom")

    # --- Personnes ---
    par_id = {p["id"]: p for p in personnes}
    fillots = defaultdict(list)
    vus = {}

    for p in personnes:
        if not p["prenom"] and not p["nom"]:
            erreurs.append(f"Ligne {p['id']} sans prénom ni nom")
            continue
        if not p["prenom"] or not p["nom"]:
            avertissements.append(f"Nom incomplet : {libelle(p)}")
        if p["promo"] not in annees:
            erreurs.append(f"Promo inconnue ({p['promo']!r}) : {libelle(p)}")

        if not est_inconnu(p):
            cle = (p["promo"], cle_nom(p["prenom"], p["nom"]))
            if cle in vus:
                erreurs.append(f"Doublon : {libelle(p)} et {libelle(vus[cle])}")
            vus[cle] = p

        parrain = p["parrain"]
        if parrain is None:
            continue
        if not isinstance(parrain, int) or parrain not in par_id:
            erreurs.append(f"Parrain non reconnu ({parrain!r}) : {libelle(p)}")
            continue
        if parrain == p["id"]:
            erreurs.append(f"Est son propre parrain : {libelle(p)}")
            continue
        fillots[parrain].append(p)
        pa = par_id[parrain]
        if isinstance(pa["promo"], int) and isinstance(p["promo"], int):
            ecart = p["promo"] - pa["promo"]
            if ecart <= 0:
                erreurs.append(f"Parrain pas plus ancien que son fillot : {libelle(pa)} -> {libelle(p)}")
            elif ecart != 1:
                avertissements.append(f"Écart de {ecart} ans entre parrain et fillot : {libelle(pa)} -> {libelle(p)}")

    # --- Cycles (A parrain de B parrain de ... A) ---
    etat = {}  # id -> "en cours" | "fini"
    for depart in par_id:
        chemin = []
        courant = depart
        while courant is not None and etat.get(courant) is None:
            etat[courant] = "en cours"
            chemin.append(courant)
            suivant = par_id[courant]["parrain"]
            courant = suivant if isinstance(suivant, int) and suivant in par_id and suivant != courant else None
        if courant is not None and etat.get(courant) == "en cours":
            boucle = chemin[chemin.index(courant):]
            erreurs.append("Cycle : " + " -> ".join(libelle(par_id[i]) for i in boucle))
        for i in chemin:
            etat[i] = "fini"

    # --- Avertissements de structure ---
    for pid, fs in fillots.items():
        if len(fs) > MAX_FILLOTS:
            avertissements.append(f"{len(fs)} fillots pour {libelle(par_id[pid])}")
    for p in personnes:
        if p["parrain"] is None and p["id"] not in fillots and not est_inconnu(p):
            avertissements.append(f"Personne isolée (ni parrain ni fillot) : {libelle(p)}")

    return erreurs, avertissements
