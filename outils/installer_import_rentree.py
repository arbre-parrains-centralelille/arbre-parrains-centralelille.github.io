"""Installe dans le document Grist l'outil de saisie de rentrée (à lancer une seule fois).

Ajoute :
- une colonne formule `cle` dans Personnes (nom normalisé, pour retrouver les parrains) ;
- une table `Import_rentree` où le BDE colle la liste « fillot / parrain » telle
  que produite par le mercato. Des formules découpent les noms, retrouvent le parrain
  dans la promo précédente et donnent un statut par ligne. Les colonnes Prénom, Nom,
  Promo, Parrain se copient ensuite d'un bloc dans Personnes.

Le script n'écrase rien : ce qui existe déjà est laissé tel quel.

Usage : python -m outils.installer_import_rentree   (variables GRIST_* dans .env)
"""

import json
import os
import urllib.request

from pipeline.sources import charger_env

TABLE = "Import_rentree"

# Normalisation partagée : accents, casse, tirets, apostrophes et « _ » ignorés.
CLE = r'''import re, unicodedata
def cle(t):
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode()
    return re.sub(r"[\s\-–—'’_]+", " ", t).strip().lower()
'''

# Découpe « Nom_Prénom » (format du mercato) ou, à défaut, « Prénom Nom ».
DECOUPE = r'''import re
s = re.sub(r"\s+", " ", $fillot_brut or "").strip()
if not re.search(r"[^\W\d_]", s):  # ligne sans lettre (ex. numéro de groupe)
    return ""
if "_" in s:
    nom, prenom = s.split("_", 1)
else:
    prenom, _, nom = s.partition(" ")
{partie} = re.sub(r"\s*-+\s*", "-", {partie}).strip()
return {partie}.title() if {partie}.isupper() else {partie}
'''

FORMULES_PERSONNES = {
    "cle": ("Text", "cle (technique)", CLE + 'return cle(f"{$prenom} {$nom}")'),
}

COLONNES_IMPORT = [
    # (id, type, libellé, formule ou None pour une colonne de saisie)
    ("fillot_brut", "Text", "Fillot (collé)", None),
    ("parrain_brut", "Text", "Parrain (collé)", None),
    ("statut", "Text", "Statut", r'''import difflib
if not $nom:
    return "Ignoré (ligne sans nom)" if $fillot_brut else ""
promo = Promos.lookupOne(promo=$promo)
if Personnes.lookupRecords(cle=$cle, promo=promo.id):
    return "✔ Déjà dans l'arbre"
if len(Import_rentree.lookupRecords(cle=$cle)) > 1:
    return "❌ Fillot en double dans l'import"
if not $cles_parrain:
    return "⚠️ Sans parrain"
if $parrain:
    if $parrain.promo.promo != $promo - 1:
        return f"⚠️ Parrain en promo {$parrain.promo.promo}, à vérifier (redoublant ?)"
    return "✅ OK"
if len($candidats) > 1:
    return "❌ Plusieurs parrains possibles : " + ", ".join(p.libelle for p in $candidats)
precedente = Personnes.lookupRecords(promo=Promos.lookupOne(promo=$promo - 1).id)
proches = difflib.get_close_matches($cles_parrain[0], [p.cle for p in precedente], n=1, cutoff=0.75)
if proches:
    p = Personnes.lookupOne(cle=proches[0], promo=Promos.lookupOne(promo=$promo - 1).id)
    return f"❌ Parrain introuvable. Vouliez-vous dire {p.prenom} {p.nom} ?"
return "❌ Parrain introuvable dans l'arbre"
'''),
    ("prenom", "Text", "Prénom", DECOUPE.format(partie="prenom")),
    ("nom", "Text", "Nom", DECOUPE.format(partie="nom")),
    ("promo", "Int", "Promo", "annees = [p.promo for p in Promos.all if p.promo]\nreturn max(annees) if annees else None"),
    ("parrain", "Ref:Personnes", "Parrain", r'''if not $candidats:
    return None
proches = [p for p in $candidats if p.promo.promo == $promo - 1]
if len(proches) == 1:
    return proches[0]
if not proches and len($candidats) == 1:
    return $candidats[0]
return None
'''),
    ("cle", "Text", "cle (technique)", CLE + 'return cle(f"{$prenom} {$nom}") if $nom else ""'),
    ("cles_parrain", "Any", "cles parrain (technique)", CLE + r'''s = re.sub(r"\s+", " ", $parrain_brut or "").strip()
if not s or "pas de parrain" in s.lower():
    return []
if "_" in s:
    nom, prenom = s.split("_", 1)
else:
    prenom, _, nom = s.partition(" ")
return list(dict.fromkeys([cle(prenom + " " + nom), cle(nom + " " + prenom)]))
'''),
    ("candidats", "RefList:Personnes", "candidats (technique)", r'''trouves = {}
for c in $cles_parrain:
    for p in Personnes.lookupRecords(cle=c):
        if $promo and p.promo.promo < $promo:
            trouves[p.id] = p
# Les parrains les plus proches de la nouvelle promo d'abord
return [p.id for p in sorted(trouves.values(), key=lambda p: -p.promo.promo)]
'''),
]


def api(methode, chemin, corps=None):
    serveur = (os.environ.get("GRIST_SERVEUR") or "https://docs.getgrist.com").rstrip("/")
    url = f"{serveur}/api/docs/{os.environ['GRIST_DOC_ID']}{chemin}"
    donnees = json.dumps(corps).encode() if corps is not None else None
    req = urllib.request.Request(url, data=donnees, method=methode, headers={
        "Authorization": f"Bearer {os.environ['GRIST_API_KEY']}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=60) as rep:
        return json.load(rep)


def colonne(id_, type_, label, formule):
    champs = {"type": type_, "label": label, "isFormula": formule is not None}
    if formule is not None:
        champs["formula"] = formule
    return {"id": id_, "fields": champs}


def main():
    charger_env()
    tables = {t["id"] for t in api("GET", "/tables")["tables"]}

    existantes = {c["id"] for c in api("GET", "/tables/Personnes/columns")["columns"]}
    a_ajouter = [colonne(i, *v) for i, v in FORMULES_PERSONNES.items() if i not in existantes]
    if a_ajouter:
        api("POST", "/tables/Personnes/columns", {"columns": a_ajouter})
        print("Personnes : colonne(s) ajoutée(s) :", ", ".join(c["id"] for c in a_ajouter))
    else:
        print("Personnes : rien à ajouter")

    if TABLE in tables:
        print(f"{TABLE} existe déjà : non modifiée")
    else:
        api("POST", "/tables", {"tables": [{"id": TABLE, "columns": [colonne(*c) for c in COLONNES_IMPORT]}]})
        print(f"{TABLE} créée")


if __name__ == "__main__":
    main()
