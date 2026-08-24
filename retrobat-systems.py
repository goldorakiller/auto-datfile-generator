import os
import re
import xml.etree.ElementTree as ET

import requests

# Config
ES_SYSTEMS_URL = "https://raw.githubusercontent.com/RetroBat-Official/retrobat-setup/master/system/templates/emulationstation/es_systems.cfg"
OUTPUT_FILE = "retrobat-systems.json"

# Un fichier genere par ce meme pipeline (dats-natifs) par systeme RetroBat
# (code court) : reunit ce que no-intro.py/redump.py/tosec.py ont deja publie
# en le rapprochant du VRAI referentiel officiel des systemes RetroBat, plutot
# que de laisser cette correspondance figee dans un fichier tiers qui se
# perime (voir historique : un fichier hors-repo avait 40/87 correspondances
# fausses des sa premiere verification).
#
# Tourne une fois par jour dans le meme run que les 3 generateurs : lit les
# manifestes qu'ils viennent de produire (deja sur disque, pas de second
# telechargement), fait le rapprochement de noms (meme algorithme que
# RBTools/RetroBat.Dat/Catalog/RomsetNameMatcher.cs, valide a 93% en reel),
# et publie un manifeste indexe par CODE SYSTEME RETROBAT — le client n'a
# plus besoin de faire ce rapprochement lui-meme, juste une consultation
# directe par cle.
MANIFESTS = {
    "No-Intro": "no-intro_parent-clone.xml",
    "Redump": "redump.xml",
    "TOSEC": "tosec.xml",
}

# Fournisseurs sans manifeste externe : chaque fichier du dossier EST son
# propre dat (voir load_loose_folder) — le nom de fichier sert de nom de
# catalogue pour le rapprochement, pas une entree d'un manifeste partage.
LOOSE_FOLDERS = {
    "Clean CPC DB": "clean-cpc-db",
    "WHDLoad": "whdload",
    "Pleasuredome MAME": "pleasuredome-mame",
    "Pleasuredome HBMAME": "pleasuredome-hbmame",
    "Pleasuredome PinMAME": "pleasuredome-pinmame",
    "Visual Pinball": "visual-pinball",
    "Future Pinball": "future-pinball",
    "FBNeo": "fbneo",
    "Libretro-database": "libretro-database-dat",
}

# eggmansworld-datfiles.py cree un sous-dossier par collection (19+, suit
# les releases de Eggmansworld/Datfiles) — chaque sous-dossier devient sa
# propre source ici, pas un dict fixe comme LOOSE_FOLDERS.
EGGMANSWORLD_ROOT = "eggmansworld-datfiles"

_QUALIFIER_RE = re.compile(r"(\s*\([^)]*\))+\s*$")
_ALT_NAME_RE = re.compile(r"\s*&.*$")
_MARKERS = {"non-redump", "redump", "source code", "unofficial"}


def normalize(s):
    s = s.lower()
    s = s.replace("&", "and")
    s = s.replace('"', "").replace("'", "").replace(".", "")
    s = re.sub(r"[-/,]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_system_part(catalog_name):
    name = _ALT_NAME_RE.sub("", catalog_name)
    name = _QUALIFIER_RE.sub("", name).strip()

    segments = [seg.strip() for seg in name.split(" - ")]
    if segments and segments[0].lower() in _MARKERS:
        segments = segments[1:]
    if len(segments) > 1:
        segments = segments[1:]  # retire le segment fabricant
    return " - ".join(segments)


def find_matches(retrobat_fullname, catalog_entries):
    """Rend TOUTES les entrees plausibles (pas juste la premiere) : plusieurs
    variantes d'un meme systeme (ex. Non-Redump vs officiel) peuvent
    legitimement matcher — c'est a l'utilisateur de choisir, pas a
    l'algorithme de trancher silencieusement."""
    target = normalize(retrobat_fullname)
    if len(target) < 3:
        return []

    exact = []
    loose = []
    for entry in catalog_entries:
        candidate = normalize(extract_system_part(entry["name"]))
        if not candidate:
            continue
        if candidate == target:
            exact.append(entry)
        elif len(candidate) >= 3 and (candidate in target or target in candidate):
            loose.append(entry)

    return exact if exact else loose


def load_es_systems():
    resp = requests.get(ES_SYSTEMS_URL, timeout=150)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    systems = []
    for system in root.findall("system"):
        name = system.findtext("name")
        fullname = system.findtext("fullname")
        if name and fullname:
            systems.append({"code": name, "fullname": fullname})
    return systems


def load_manifest(path):
    if not os.path.exists(path):
        return []
    tree = ET.parse(path)
    entries = []
    for datfile in tree.getroot().findall("datfile"):
        entries.append({
            "name": datfile.findtext("name") or "",
            "version": datfile.findtext("version") or "",
            "url": datfile.findtext("url") or "",
            "file": datfile.findtext("file") or "",
        })
    return entries


def load_loose_folder(folder):
    """Pas de manifeste : chaque fichier .dat/.xml du dossier est lui-meme
    un catalogue a une seule entree — son nom de fichier (sans extension)
    sert de nom pour le rapprochement, son URL brute est deja publiee par
    le script qui a rempli ce dossier plus tot dans le meme run."""
    if not os.path.isdir(folder):
        return []

    repo = os.environ.get("GITHUB_REPOSITORY", "goldorakiller/auto-datfile-generator")
    entries = []
    for filename in sorted(os.listdir(folder)):
        if not (filename.lower().endswith(".dat") or filename.lower().endswith(".xml")):
            continue
        entries.append({
            "name": os.path.splitext(filename)[0],
            "version": "",
            "url": f"https://raw.githubusercontent.com/{repo}/master/{folder}/{filename}",
            "file": filename,
        })
    return entries


def load_eggmansworld_collections():
    """Une source par sous-dossier (une par collection Eggmansworld) plutot
    qu'une seule source "Eggmansworld" fourre-tout — chaque collection a son
    propre theme (laserdisc, hvsc, touhou...), pas comparable entre elles."""
    catalogs = {}
    if not os.path.isdir(EGGMANSWORLD_ROOT):
        return catalogs

    for tag in sorted(os.listdir(EGGMANSWORLD_ROOT)):
        folder = os.path.join(EGGMANSWORLD_ROOT, tag)
        if not os.path.isdir(folder):
            continue
        catalogs[f"Eggmansworld - {tag}"] = load_loose_folder(folder)
    return catalogs


def build():
    print("Loading official RetroBat systems list ...")
    systems = load_es_systems()
    print(f"{len(systems)} systems")

    catalogs = {}
    for source, filename in MANIFESTS.items():
        entries = load_manifest(filename)
        catalogs[source] = entries
        print(f"{source}: {len(entries)} entries ({filename})")

    for source, folder in LOOSE_FOLDERS.items():
        entries = load_loose_folder(folder)
        catalogs[source] = entries
        print(f"{source}: {len(entries)} entries ({folder}/)")

    eggmansworld_catalogs = load_eggmansworld_collections()
    for source, entries in eggmansworld_catalogs.items():
        catalogs[source] = entries
    print(f"Eggmansworld: {len(eggmansworld_catalogs)} collection(s)")

    results = []
    matched_count = 0
    for system in systems:
        candidates = []
        for source, entries in catalogs.items():
            for entry in find_matches(system["fullname"], entries):
                candidates.append({
                    "Source": source,
                    "Name": entry["name"],
                    "Version": entry["version"],
                    "Url": entry["url"],
                    "File": entry["file"],
                })

        if candidates:
            matched_count += 1

        results.append({
            "SystemCode": system["code"],
            "FullName": system["fullname"],
            "Candidates": candidates,
        })

    print(f"\n{matched_count}/{len(systems)} systemes avec au moins un candidat")

    import json
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUTPUT_FILE}")


try:
    build()
except KeyboardInterrupt:
    pass
