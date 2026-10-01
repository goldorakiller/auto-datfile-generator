import glob
import os
import xml.etree.ElementTree as ET

from dat_output_dir import replace_directory

# Sous-ensembles de collections Eggmansworld, fabriques ici (pas un mirror) a
# partir des dats deja telecharges par eggmansworld-datfiles.py plus tot dans
# le meme run : une collection Eggmansworld melange souvent les jeux avec des
# BIOS, l'emulateur, des scans et des outils, alors qu'un systeme RetroBat
# n'attend que les jeux dans roms\<systeme>. Assigner la collection entiere
# ferait attendre tout le reste dans ce dossier (et un Fix y enverrait les
# fichiers de l'utilisateur dans ToSort).
#
# Chaque sous-ensemble garde les jeux de certains dossiers (<dir>) de la
# collection, remis A PLAT (le rangement de la collection n'a pas de sens dans
# roms\<systeme>), et peut imposer le rangement ROMVault (forcepacking).
#
# Si le dat source manque, le sous-ensemble n'est pas regenere et la version
# de la veille reste en place (replace_directory).

SOURCE_DIR = "Eggmansworld - Datfiles"
OUTPUT_DIR = "eggmansworld-subsets"

# (nom du dat produit, nom de la collection source, dossiers gardes,
#  forcepacking ROMVault ou None, description)
SUBSETS = [
    # Systeme RetroBat "laseractive" (emulateur ares) : UN fichier .mmi de 30 a
    # 83 Go par disque. forcepacking "fileonly" : ROMVault ne doit jamais les
    # zipper (il le ferait sinon, ce format n'etant pas reconnu comme disque).
    # Les BIOS vont dans le dossier bios de RetroBat, pas dans roms\.
    ("Ares - LaserActive Discs", "Ares",
     ("Discs - MegaLD (Sega)", "Discs - LDROM2 (NEC)"),
     "fileonly",
     "LaserActive discs only (Mega-LD and LD-ROM2), without BIOS, emulator, extras and tools"),
]


def _source_path(collection):
    # Nom date "Ares (2026-09-01_RomVault).xml" : la plus recente.
    candidates = sorted(glob.glob(os.path.join(SOURCE_DIR, f"{glob.escape(collection)} (*).*")))
    candidates = [c for c in candidates if c.lower().endswith((".xml", ".dat"))]
    return candidates[-1] if candidates else None


def _games_in_dirs(root, wanted_dirs):
    """Jeux des dossiers voulus, a n'importe quelle profondeur sous ces dossiers."""
    games = []

    def walk(node, inside):
        for child in node:
            if child.tag == "dir":
                walk(child, inside or child.get("name") in wanted_dirs)
            elif child.tag in ("game", "machine") and inside:
                games.append(child)

    walk(root, False)
    return games


def _text(header, tag):
    child = header.find(tag) if header is not None else None
    return (child.text or "").strip() if child is not None and child.text else ""


def build():
    with replace_directory(OUTPUT_DIR) as out_dir:
        for name, collection, dirs, packing, note in SUBSETS:
            source = _source_path(collection)
            if source is None:
                raise RuntimeError(f"Collection {collection} absente de {SOURCE_DIR}/")

            root = ET.parse(source).getroot()
            header = root.find("header")
            games = _games_in_dirs(root, set(dirs))
            if not games:
                raise RuntimeError(f"{name} : aucun jeu dans {dirs} ({source})")

            out = ET.Element("datafile")
            out_header = ET.SubElement(out, "header")
            for tag, value in [
                ("name", name),
                ("description", f"{_text(header, 'name') or collection} - {note}"),
                ("category", _text(header, "category")),
                ("version", _text(header, "version")),
                ("date", _text(header, "date")),
                ("author", _text(header, "author")),
                ("homepage", _text(header, "homepage")),
                ("url", _text(header, "url")),
                ("comment", f"Subset built by auto-datfile-generator (eggmansworld-subsets.py) from {os.path.basename(source)}"),
            ]:
                if value:
                    ET.SubElement(out_header, tag).text = value
            if packing:
                ET.SubElement(out_header, "romvault", {"forcepacking": packing})

            out.extend(games)
            ET.indent(out, space="\t")
            path = os.path.join(out_dir, f"{name}.xml")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write('<?xml version="1.0"?>\n')
                f.write(ET.tostring(out, encoding="unicode"))
                f.write("\n")

            size = sum(int(r.get("size") or 0) for g in games for r in g.iter("rom"))
            print(f"{name} : {len(games)} jeu(x), {size / 1e9:.0f} Go -> {path} (source {source})")


try:
    build()
except KeyboardInterrupt:
    pass
