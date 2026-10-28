"""Installe ou met à jour dans le document Grist l'outil de saisie de rentrée.

Ajoute :
- une colonne formule `cle` dans Personnes (nom normalisé, pour retrouver les parrains) ;
- une table `Import_rentree` où le BDE colle la liste « fillot / parrain » telle
  que produite par le mercato. Des formules découpent les noms, retrouvent le parrain
  (en tolérant fautes de frappe, casse, accents, ordre prénom/nom) et donnent un
  statut par ligne. Les colonnes Prénom, Nom, Promo, Parrain se copient ensuite
  d'un bloc dans Personnes.

Relançable sans risque : crée ce qui manque et met à jour les formules ; les colonnes
de saisie (ce que le BDE a collé) ne sont jamais touchées.

Usage : python -m outils.installer_import_rentree   (variables GRIST_* dans .env)
"""

import json
import os
import urllib.request

from pipeline.sources import charger_env

TABLE = "Import_rentree"

# Normalisation partagée : accents, casse, tirets, apostrophes, parenthèses et « _ »
# ignorés. Les séparateurs sont remplacés AVANT la conversion ASCII, sinon « ’ » et
# « – » disparaîtraient en collant les mots (« D’Hu » -> « dhu » au lieu de « d hu »).
CLE = r'''import re, unicodedata
def cle(t):
    t = re.sub(r"[\s\-–—'’_()]+", " ", t or "")
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().lower()
'''

# Découpe « Nom_Prénom » (format du mercato) ou, à défaut, « Prénom Nom ».
# Les commentaires entre parenthèses sont retirés.
DECOUPE = r'''import re
s = re.sub(r"\(.*\)", " ", $fillot_brut or "")
s = re.sub(r"\s+", " ", s).strip()
if not re.search(r"[^\W\d_]", s):  # ligne sans lettre (ex. numéro de groupe)
    return ""
if "_" in s:
    nom, prenom = s.split("_", 1)
else:
    prenom, _, nom = s.partition(" ")
{partie} = re.sub(r"\s*-+\s*", "-", {partie}).strip()
return {partie}.title() if {partie}.isupper() or {partie}.islower() else {partie}
'''

FORMULES_PERSONNES = [
    ("cle", "Text", "cle (technique)", CLE + 'return cle(f"{$prenom} {$nom}")'),
    # Case à cocher : un redoublant parraine deux promos après la sienne sans que ce
    # soit signalé comme une anomalie.
    ("redoublant", "Bool", "Redoublant", None),
]

STATUT = r'''def nom_complet(p):
    return f"{p.prenom} {p.nom} ({p.promo.promo})"
if not $nom:
    return "Ignoré (ligne sans nom)" if $fillot_brut else ""
if not $promo:
    return "❌ Aucune promo dans la table Promos"
promo = Promos.lookupOne(promo=$promo)
if Personnes.lookupRecords(cle=$cle, promo=promo.id):
    return "✔ Déjà dans l'arbre"
if len(Import_rentree.lookupRecords(cle=$cle)) > 1:
    return "❌ Fillot en double dans l'import"
if not $cles_parrain:
    return "⚠️ Sans parrain"
if not $parrain:
    meme_promo = [p for c in $cles_parrain for p in Personnes.lookupRecords(cle=c, promo=promo.id)]
    if meme_promo:
        p = meme_promo[0]
        return (f"❌ {p.prenom} {p.nom} est en promo {$promo}, comme le fillot. "
                "As-tu ajouté la nouvelle promo dans la table Promos ?")
    if len($candidats) > 1:
        return "❌ Plusieurs parrains possibles : " + ", ".join(nom_complet(p) for p in $candidats)
    return "❌ Parrain introuvable : ajoute-le d'abord dans Personnes, ou corrige son nom ici"
if $parrain.id not in [c.id for c in $candidats]:
    return f"⚠️ Parrain reconnu malgré une différence d'écriture : {nom_complet($parrain)}, à vérifier"
if $parrain.promo.promo == $promo - 2 and $parrain.redoublant:
    return "✅ OK (parrain redoublant)"
if $parrain.promo.promo != $promo - 1:
    return f"⚠️ Parrain en promo {$parrain.promo.promo}, à vérifier (redoublant ? coche la case dans Personnes)"
return "✅ OK"
'''

PARRAIN = r'''import difflib
if not $cles_parrain or not $promo:
    return None
# 1. Correspondance exacte (après normalisation), de préférence dans la promo précédente
proches = [p for p in $candidats if p.promo.promo == $promo - 1]
if len(proches) == 1:
    return proches[0]
if proches or len($candidats) > 1:
    return None  # ambigu : le statut liste les candidats
if $candidats:
    return $candidats[0]
# 2. Sinon, tolérance aux fautes de frappe et aux noms incomplets, uniquement si
#    une seule personne de la promo précédente correspond nettement.
precedente = Personnes.lookupRecords(promo=Promos.lookupOne(promo=$promo - 1).id)
scores = []
for p in precedente:
    score = max(difflib.SequenceMatcher(None, c, p.cle).ratio() for c in $cles_parrain)
    mots_p = set(p.cle.split())
    for c in $cles_parrain:
        mots = set(c.split())
        if len(mots) >= 2 and (mots <= mots_p or mots_p <= mots):
            score = max(score, 0.9)  # ex. « Esther Zhou » dans « Wenrui (Esther) Zhou »
    scores.append((score, p))
scores.sort(key=lambda x: -x[0])
if scores and scores[0][0] >= 0.85 and (len(scores) == 1 or scores[0][0] - scores[1][0] >= 0.05):
    return scores[0][1]
return None
'''

COLONNES_IMPORT = [
    # (id, type, libellé, formule ou None pour une colonne de saisie)
    ("fillot_brut", "Text", "Fillot (collé)", None),
    ("parrain_brut", "Text", "Parrain (collé)", None),
    ("statut", "Text", "Statut", STATUT),
    ("prenom", "Text", "Prénom", DECOUPE.format(partie="prenom")),
    ("nom", "Text", "Nom", DECOUPE.format(partie="nom")),
    ("promo", "Int", "Promo", "annees = [p.promo for p in Promos.all if p.promo]\nreturn max(annees) if annees else None"),
    ("parrain", "Ref:Personnes", "Parrain", PARRAIN),
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
    with urllib.request.urlopen(req, timeout=120) as rep:
        texte = rep.read()
        return json.loads(texte) if texte else None


def colonne(id_, type_, label, formule):
    # untieColIdFromLabel : sans ça, Grist renomme l'identifiant de la colonne quand
    # on change son libellé (« cle » -> « cle_technique_ »), et les formules cassent.
    champs = {"type": type_, "label": label, "isFormula": formule is not None, "untieColIdFromLabel": True}
    if formule is not None:
        champs["formula"] = formule
    return {"id": id_, "fields": champs}


def synchroniser(table, colonnes):
    """Crée les colonnes manquantes et met à jour les formules des colonnes existantes."""
    existantes = {c["id"]: c["fields"]["label"] for c in api("GET", f"/tables/{table}/columns")["columns"]}
    # Réparation : colonne renommée par Grist -> on lui rend son identifiant
    par_label = {label: id_ for id_, label in existantes.items()}
    renommages = [
        {"id": par_label[label], "fields": {"untieColIdFromLabel": True, "colId": id_}}
        for id_, _, label, _ in colonnes
        if id_ not in existantes and label in par_label and par_label[label] != id_
    ]
    if renommages:
        api("PATCH", f"/tables/{table}/columns", {"columns": renommages})
        existantes = {c["id"]: c["fields"]["label"] for c in api("GET", f"/tables/{table}/columns")["columns"]}
    a_creer = [colonne(*c) for c in colonnes if c[0] not in existantes]
    a_maj = [colonne(*c) for c in colonnes if c[0] in existantes and c[3] is not None]
    if a_creer:
        api("POST", f"/tables/{table}/columns", {"columns": a_creer})
    if a_maj:
        api("PATCH", f"/tables/{table}/columns", {"columns": a_maj})
    print(f"{table} : {len(renommages)} réparée(s), {len(a_creer)} créée(s), {len(a_maj)} formule(s) mise(s) à jour")


def main():
    charger_env()
    tables = {t["id"] for t in api("GET", "/tables")["tables"]}
    synchroniser("Personnes", FORMULES_PERSONNES)
    if TABLE in tables:
        synchroniser(TABLE, COLONNES_IMPORT)
    else:
        api("POST", "/tables", {"tables": [{"id": TABLE, "columns": [colonne(*c) for c in COLONNES_IMPORT]}]})
        print(f"{TABLE} créée")


if __name__ == "__main__":
    main()
