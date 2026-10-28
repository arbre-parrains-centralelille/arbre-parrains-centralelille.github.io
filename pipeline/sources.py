"""Lecture des données depuis une source (Grist ou CSV local).

Chaque source renvoie le même format, ce qui permet de changer d'outil de saisie
sans toucher à la validation ni au site :

    promos    : liste de {"id", "promo", "nom"}
    personnes : liste de {"id", "prenom", "nom", "promo", "parrain"}
                promo   = année (int) ou valeur brute non reconnue
                parrain = id (int) d'une personne, None si pas de parrain,
                          ou valeur brute (str) si la référence est cassée
"""

import csv
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

TABLE_PERSONNES = "Personnes"
TABLE_PROMOS = "Promos"


def charger_env(chemin=RACINE / ".env"):
    """Charge un fichier .env (CLE=valeur) dans os.environ, sans écraser l'existant."""
    if not chemin.exists():
        return
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith("#") and "=" in ligne:
            cle, valeur = ligne.split("=", 1)
            os.environ.setdefault(cle.strip(), valeur.strip().strip('"'))


def _texte(v):
    return "" if v is None else str(v).strip()


def _entier(v):
    """2027, 2027.0 ou "2027" -> 2027 ; sinon renvoie la valeur telle quelle."""
    if isinstance(v, bool):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    return v


# --- Grist ---------------------------------------------------------------------

class ErreurGrist(Exception):
    pass


EXPLICATIONS_HTTP = {
    401: "clé API refusée : vérifie GRIST_API_KEY (copiée en entier, sans espace ni retour à la ligne)",
    403: "accès refusé : le compte de la clé API n'a pas accès à ce document",
    404: "document ou table introuvable : vérifie GRIST_DOC_ID, GRIST_SERVEUR et le nom de la table",
}


def _grist_records(serveur, doc_id, table, cle_api):
    url = f"{serveur.rstrip('/')}/api/docs/{doc_id}/tables/{table}/records"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {cle_api}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as rep:
            return json.load(rep)["records"]
    except urllib.error.HTTPError as e:
        detail = EXPLICATIONS_HTTP.get(e.code, e.read().decode(errors="replace")[:300])
        raise ErreurGrist(f"Grist a répondu {e.code} pour la table {table} ({url}) : {detail}") from None
    except urllib.error.URLError as e:
        raise ErreurGrist(f"Serveur Grist injoignable ({serveur}) : {e.reason}") from None


def lire_grist():
    charger_env()
    config = {}
    for nom in ("GRIST_DOC_ID", "GRIST_API_KEY"):
        config[nom] = os.environ.get(nom, "").strip()
        if not config[nom]:
            raise ErreurGrist(f"Variable {nom} absente ou vide (fichier .env en local, Settings > Secrets and variables sur GitHub)")
    serveur = os.environ.get("GRIST_SERVEUR", "").strip() or "https://docs.getgrist.com"
    doc_id, cle_api = config["GRIST_DOC_ID"], config["GRIST_API_KEY"]

    promos = []
    for r in _grist_records(serveur, doc_id, TABLE_PROMOS, cle_api):
        f = r["fields"]
        promos.append({"id": r["id"], "promo": _entier(f.get("promo")), "nom": _texte(f.get("nom"))})
    annee_par_id = {p["id"]: p["promo"] for p in promos}

    personnes = []
    for r in _grist_records(serveur, doc_id, TABLE_PERSONNES, cle_api):
        f = r["fields"]
        promo = _entier(f.get("promo"))
        # Colonne Reference -> id de ligne dans Promos. On accepte aussi une année
        # directe, au cas où la colonne serait restée numérique.
        if isinstance(promo, int) and promo in annee_par_id and promo < 1900:
            promo = annee_par_id[promo]
        parrain = f.get("parrain")
        # Grist renvoie 0 pour une référence vide, et le texte saisi si la référence
        # ne correspond à aucune ligne.
        if parrain in (0, None, ""):
            parrain = None
        personnes.append({
            "id": r["id"],
            "prenom": _texte(f.get("prenom")),
            "nom": _texte(f.get("nom")),
            "promo": promo,
            "parrain": parrain,
        })
    return promos, personnes


# --- CSV local (fichiers d'import Grist) ----------------------------------------

def lire_csv(dossier=RACINE / "data" / "grist_import"):
    """Lit promos.csv et personnes.csv (parrain désigné par « Prénom Nom (promo) »).

    Les id sont attribués dans l'ordre des lignes, comme le ferait Grist à l'import.
    """
    dossier = Path(dossier)
    with (dossier / "promos.csv").open(encoding="utf-8") as f:
        promos = [
            {"id": i, "promo": _entier(r["promo"]), "nom": _texte(r["nom"])}
            for i, r in enumerate(csv.DictReader(f), start=1)
        ]
    with (dossier / "personnes.csv").open(encoding="utf-8") as f:
        lignes = list(csv.DictReader(f))

    def libelle(r):
        return " ".join(x for x in (r["prenom"].strip(), r["nom"].strip()) if x) + f" ({r['promo'].strip()})"

    id_par_libelle = {libelle(r): i for i, r in enumerate(lignes, start=1)}
    personnes = []
    for i, r in enumerate(lignes, start=1):
        parrain = _texte(r["parrain"])
        personnes.append({
            "id": i,
            "prenom": _texte(r["prenom"]),
            "nom": _texte(r["nom"]),
            "promo": _entier(r["promo"]),
            "parrain": id_par_libelle.get(parrain, parrain) if parrain else None,
        })
    return promos, personnes
