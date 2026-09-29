import glob
import os
import re
import xml.etree.ElementTree as ET

from dat_output_dir import replace_directory

# Sous-ensembles arcade PAR CARTE, fabriques ici (aucune source ne les
# publie) a partir de deux dats deja mirrores plus tot dans le meme run :
# - fbneo/FinalBurn Neo (ClrMame Pro XML, Arcade only).dat -> fbneo-subsets/
# - pleasuredome-mame/MAME <version> ROMs (non-merged).xml -> mame-subsets/
#
# Les deux indiquent, pour chaque jeu, le fichier source de son pilote
# (attribut sourcefile, ex. "cave/d_dodonpachi.cpp" chez FBNeo,
# "atlus/cave.cpp" chez MAME) : c'est le seul critere fiable pour dire a
# quelle carte appartient un jeu (le fabricant ne suffit pas : Capcom a fait
# bien plus que du CPS). Besoin : les systemes RetroBat "cave", "cps1",
# "cps2", "cps3", "model2"... n'avaient aucun dat, un dat FBNeo/MAME complet
# (8 000 / 43 000 jeux) ferait attendre tout l'arcade dans roms\cps1.
#
# FBNeo : on garde aussi les parents (cloneof) et les BIOS (romof) des jeux
# retenus, sinon ROMVault ne pourrait pas verifier un clone ni un jeu PGM.
# MAME : le set non-merged est complet par jeu (roms du parent ET du BIOS
# incluses, verifie sur 1on1gov/coh1002m), et les dats Pleasuredome ne
# decrivent pas les liens parent/clone : aucun jeu n'en depend, on filtre
# simplement ; BIOS, devices et machines non jouables sont ecartes.
#
# Si un des deux dats sources manque (telechargement rate aujourd'hui ET
# jamais reussi avant), ses sous-ensembles ne sont pas regeneres et la
# version de la veille reste en place (replace_directory).

FBNEO_SOURCE = os.path.join("fbneo", "FinalBurn Neo (ClrMame Pro XML, Arcade only).dat")
MAME_SOURCE_GLOB = os.path.join("pleasuredome-mame", "MAME * ROMs (non-merged).xml")
FBNEO_OUTPUT_DIR = "fbneo-subsets"
MAME_OUTPUT_DIR = "mame-subsets"


def _cave_pgm(sourcefile, manufacturer, prefix):
    # Jeux CAVE sortis sur carte PGM d'IGS (DoDonPachi Dai-Ou-Jou, Ketsui,
    # Espgaluda) : ranges avec CAVE comme dans les collections habituelles.
    # Progear (CPS-2, "Capcom / Cave") reste volontairement dans cps2.
    return sourcefile.startswith(prefix) and manufacturer.startswith("Cave")


# Nom du sous-ensemble -> regle FBNeo / regle MAME (None = pas de version).
# Une regle recoit (sourcefile, fabricant) et dit si le jeu en fait partie.
SUBSETS = [
    ("CAVE",
     lambda s, m: s.startswith("cave/") or _cave_pgm(s, m, "pgm/"),
     lambda s, m: s in ("atlus/cave.cpp", "cave/cv1k.cpp") or _cave_pgm(s, m, "igs/pgm.cpp")),
    ("CPS-1",
     lambda s, m: s == "capcom/d_cps1.cpp",
     lambda s, m: s in ("capcom/cps1.cpp", "capcom/cps1bl_5205.cpp", "capcom/cps1bl_pic.cpp", "capcom/fcrash.cpp")),
    ("CPS-2",
     lambda s, m: s == "capcom/d_cps2.cpp",
     lambda s, m: s == "capcom/cps2.cpp"),
    ("CPS-3",
     lambda s, m: s == "cps3/d_cps3.cpp",
     lambda s, m: s == "capcom/cps3.cpp"),
    ("Model 2", None, lambda s, m: s == "sega/model2.cpp"),
    ("Model 3", None, lambda s, m: s == "sega/model3.cpp"),
    ("Hikaru", None, lambda s, m: s == "sega/hikaru.cpp"),
    ("ZN (Zinc)", None, lambda s, m: s == "sony/zn.cpp"),
    # Gaelco PowerVR (Demul) = la carte d'ATV Track / Smashing Drive, pas
    # toutes les cartes Gaelco (Radikal Bikers, Big Karnak... sont ailleurs).
    ("Gaelco PowerVR", None, lambda s, m: s == "gaelco/atvtrack.cpp"),
]


def _text(elem, tag):
    child = elem.find(tag)
    return (child.text or "").strip() if child is not None and child.text else ""


def _write_dat(path, header_fields, games, doctype):
    root = ET.Element("datafile")
    header = ET.SubElement(root, "header")
    for tag, value in header_fields:
        if value:
            ET.SubElement(header, tag).text = value
    root.extend(games)
    ET.indent(root, space="\t")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write('<?xml version="1.0"?>\n')
        f.write(doctype + "\n")
        f.write(ET.tostring(root, encoding="unicode"))
        f.write("\n")


def _subset_header(source_header, subset, source_label, rule_note):
    return [
        ("name", f"{source_label} - {subset}"),
        ("description", f"{_text(source_header, 'description') or source_label} - {subset} ({rule_note})"),
        ("category", _text(source_header, "category")),
        ("version", _text(source_header, "version")),
        ("date", _text(source_header, "date")),
        ("author", _text(source_header, "author")),
        ("homepage", _text(source_header, "homepage")),
        ("url", _text(source_header, "url")),
        ("comment", "Subset by board built by auto-datfile-generator (arcade-subsets.py) "
                    "from the sourcefile attribute of each game"),
    ]


def build_fbneo():
    if not os.path.exists(FBNEO_SOURCE):
        print(f"{FBNEO_SOURCE} absent : sous-ensembles FBNeo non regeneres")
        return

    root = ET.parse(FBNEO_SOURCE).getroot()
    games = root.findall("game")
    by_name = {g.get("name"): g for g in games}
    print(f"FBNeo : {len(games)} jeux dans {FBNEO_SOURCE}")

    with replace_directory(FBNEO_OUTPUT_DIR) as out_dir:
        for subset, fbneo_rule, _ in SUBSETS:
            if fbneo_rule is None:
                continue

            wanted = {g.get("name") for g in games
                      if fbneo_rule(g.get("sourcefile", ""), _text(g, "manufacturer"))}
            picked = len(wanted)

            # Parents et BIOS, jusqu'au bout de la chaine (un BIOS peut lui-meme
            # dependre d'un autre).
            pending = list(wanted)
            while pending:
                game = by_name.get(pending.pop())
                if game is None:
                    continue
                for ref in (game.get("cloneof"), game.get("romof")):
                    if ref and ref not in wanted and ref in by_name:
                        wanted.add(ref)
                        pending.append(ref)

            # Ordre du dat d'origine (alphabetique chez FBNeo).
            kept = [g for g in games if g.get("name") in wanted]
            path = os.path.join(out_dir, f"FBNeo - {subset}.dat")
            _write_dat(path, _subset_header(root.find("header"), subset, "FinalBurn Neo", "by board"), kept,
                       '<!DOCTYPE datafile PUBLIC "-//FinalBurn Neo//DTD ROM Management Datafile//EN" '
                       '"http://www.logiqx.com/Dats/datafile.dtd">')
            print(f"  {subset} : {picked} jeu(x) + {len(kept) - picked} parent(s)/BIOS -> {path}")


def _mame_source():
    def version_key(path):
        m = re.search(r"MAME ([\d.]+) ROMs", os.path.basename(path))
        return [int(p) for p in m.group(1).split(".")] if m else []

    candidates = sorted(glob.glob(MAME_SOURCE_GLOB), key=version_key)
    return candidates[-1] if candidates else None


def build_mame():
    source = _mame_source()
    if source is None:
        print(f"{MAME_SOURCE_GLOB} absent : sous-ensembles MAME non regeneres")
        return

    rules = [(subset, rule) for subset, _, rule in SUBSETS if rule is not None]
    kept = {subset: [] for subset, _ in rules}
    header = None
    total = 0

    # ~50 Mo : lecture en flux, chaque machine est liberee apres examen.
    for _, elem in ET.iterparse(source, events=("end",)):
        if elem.tag == "header":
            header = elem
            continue
        if elem.tag not in ("machine", "game"):
            continue

        total += 1
        playable = (elem.get("isbios") != "yes" and elem.get("isdevice") != "yes"
                    and elem.get("runnable") != "no")
        if playable:
            sourcefile = elem.get("sourcefile", "")
            manufacturer = _text(elem, "manufacturer")
            for subset, rule in rules:
                if rule(sourcefile, manufacturer):
                    kept[subset].append(elem)
                    break
            else:
                elem.clear()
        else:
            elem.clear()

    print(f"MAME : {total} machines dans {source}")

    with replace_directory(MAME_OUTPUT_DIR) as out_dir:
        for subset, _ in rules:
            path = os.path.join(out_dir, f"MAME - {subset}.xml")
            _write_dat(path, _subset_header(header, subset, "MAME", "by board, non-merged"), kept[subset],
                       '<!DOCTYPE datafile PUBLIC "-//Logiqx//DTD ROM Management Datafile//EN" '
                       '"http://www.logiqx.com/Dats/datafile.dtd">')
            print(f"  {subset} : {len(kept[subset])} jeu(x) -> {path}")


try:
    build_fbneo()
    build_mame()
except KeyboardInterrupt:
    pass
