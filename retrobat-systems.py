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


def build():
    print("Loading official RetroBat systems list ...")
    systems = load_es_systems()
    print(f"{len(systems)} systems")

    catalogs = {}
    for source, filename in MANIFESTS.items():
        entries = load_manifest(filename)
        catalogs[source] = entries
        print(f"{source}: {len(entries)} entries ({filename})")

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
