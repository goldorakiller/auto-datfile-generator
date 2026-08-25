import json
import re
import xml.etree.ElementTree as ET

import requests

from dat_catalog import load_all_catalogs

# Config
ES_SYSTEMS_URL = "https://raw.githubusercontent.com/RetroBat-Official/retrobat-setup/master/system/templates/emulationstation/es_systems.cfg"
OUTPUT_FILE = "retrobat-systems-discovered.json"

# Outil MANUEL, lance a la demande (jamais depuis daily-rebuild.yml) : fait
# le rapprochement automatique par nom entre le referentiel officiel des
# systemes RetroBat et tous les catalogues mirrores, et ECRIT SES
# PROPOSITIONS DANS UN FICHIER A PART (retrobat-systems-discovered.json) —
# ne touche jamais retrobat-systems.json, qui est desormais curate a la
# main (voir retrobat-systems.py pour son rafraichissement automatique).
#
# Raison d'etre de cette separation : le rapprochement automatique est
# fragile (un renommage upstream, un mot trop generique, une regex trop
# stricte peuvent casser un systeme entier du jour au lendemain). Ses
# resultats sont donc une PROPOSITION a relire, pas une decision a publier
# telle quelle.

_QUALIFIER_RE = re.compile(r"(\s*\([^)]*\))+\s*$")
_ALT_NAME_RE = re.compile(r"\s*&.*$")
_MARKERS = {"non-redump", "redump", "source code", "unofficial"}

# Categories de contenu qui ne correspondent jamais a un "systeme" au sens
# RetroBat (magazines scannes, extras, musique...) — pour en exclure une
# nouvelle, il suffit d'ajouter le mot ici, aucune autre modification
# necessaire. Teste sur le nom BRUT du catalogue (avant normalisation),
# insensible a la casse.
EXCLUDED_KEYWORDS = {
    "magazines",
}

# Codes systeme RetroBat trop generiques/ambigus pour un rapprochement
# automatique fiable ("flash" est un mot anglais courant qui matche plein
# de choses sans rapport — Acorn Flash Media, Compact Flash, Touhou Flash
# Project... aucun n'est le bon systeme) — pour en exclure un autre, il
# suffit d'ajouter son code ici, meme mecanique que EXCLUDED_KEYWORDS mais
# cote systeme RetroBat plutot que cote catalogue.
EXCLUDED_SYSTEMS = {
    "flash",
}


def is_excluded(raw_name):
    lowered = raw_name.lower()
    return any(keyword in lowered for keyword in EXCLUDED_KEYWORDS)


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


def _contains_token_sequence(haystack_tokens, needle_tokens):
    """needle_tokens apparait tel quel (mots consecutifs) dans
    haystack_tokens. Compare des MOTS entiers, jamais des sous-chaines de
    caracteres — "mame" ne doit jamais matcher "hbmame" ou "pinmame"."""
    if not needle_tokens or len(needle_tokens) > len(haystack_tokens):
        return False
    n = len(needle_tokens)
    return any(
        haystack_tokens[i:i + n] == needle_tokens
        for i in range(len(haystack_tokens) - n + 1)
    )


def find_matches(retrobat_fullname, catalog_entries):
    """Rend TOUTES les entrees plausibles (pas juste la premiere) : plusieurs
    variantes d'un meme systeme (ex. Non-Redump vs officiel) peuvent
    legitimement matcher — c'est a l'utilisateur de choisir, pas a
    l'algorithme de trancher silencieusement."""
    target = normalize(retrobat_fullname)
    if len(target) < 3:
        return []
    target_tokens = target.split()

    exact = []
    loose = []
    for entry in catalog_entries:
        if is_excluded(entry["name"]):
            continue

        candidate = normalize(extract_system_part(entry["name"]))
        if not candidate:
            continue
        candidate_tokens = candidate.split()

        if candidate == target:
            exact.append(entry)
        elif len(candidate) >= 3 and (
            _contains_token_sequence(candidate_tokens, target_tokens)
            or _contains_token_sequence(target_tokens, candidate_tokens)
        ):
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


def discover():
    print("Loading official RetroBat systems list ...")
    systems = load_es_systems()
    print(f"{len(systems)} systems")

    catalogs = load_all_catalogs()

    results = []
    matched_count = 0
    for system in systems:
        candidates = []
        if system["code"] not in EXCLUDED_SYSTEMS:
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

    print(f"\n{matched_count}/{len(systems)} systemes avec au moins un candidat propose")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUTPUT_FILE} — a relire et fusionner a la main dans retrobat-systems.json, jamais ecrase automatiquement")


try:
    discover()
except KeyboardInterrupt:
    pass
