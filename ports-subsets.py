import copy
import glob
import json
import os
import re
import xml.etree.ElementTree as ET

from dat_output_dir import replace_directory
from http_session import github_api_headers, retrying_session

# DAT des portages PC qui n'acceptent que CERTAINES ROM (systemes RetroBat soh,
# 2ship, starship, ghostship, pdark, dusklight), fabriques ici (pas un mirror)
# a partir des dats No-Intro et Redump deja telecharges plus tot dans le meme
# run. Assigner le dat No-Intro Nintendo 64 entier ferait attendre les ~1 000
# jeux N64 dans roms\soh ; ces portages ne savent lire qu'une poignee de
# versions precises d'UN jeu.
#
# Chaque portage publie lui-meme la liste des ROM qu'il accepte : elle est
# relue a chaque run (une version ajoutee par le portage suit sans toucher a ce
# script), puis rapprochee des dats par empreinte (SHA-1 ou MD5), jamais par
# nom. Une empreinte de la liste absente des dats (version debug introuvable,
# ROM decompressee produite par les outils du portage) est simplement listee
# dans le journal.
#
# Si une liste ou un dat source manque, rien n'est regenere et la version de
# la veille reste en place (replace_directory).

OUTPUT_DIR = "ports-subsets"

# Dats sources : (dossier, debut du nom). Le plus recent est pris : no-intro/
# garde plusieurs versions datees d'un meme dat. Jamais la variante
# "(Parent-Clone)" : ses liens clone/parent viseraient des jeux non gardes.
SOURCES = {
    "n64": ("no-intro", "Nintendo - Nintendo 64 (BigEndian) ("),
    "ique": ("no-intro", "iQue - iQue (Decrypted) ("),
    "gamecube": ("redump", "Nintendo - GameCube - Datfile ("),
    "wii": ("redump", "Nintendo - Wii - Datfile ("),
}


def _github_file(session, repo, path):
    """Contenu brut d'un fichier sur la branche par defaut du depot (l'API le
    resout : develop, main ou master selon le portage)."""
    headers = dict(github_api_headers(), Accept="application/vnd.github.raw")
    resp = session.get(f"https://api.github.com/repos/{repo}/contents/{path}", headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.text


def _supported_hashes_json(session, repo):
    # docs/supportedHashes.json des portages HarbourMasters : [{"name", "sha1"}].
    return {e["sha1"].lower() for e in json.loads(_github_file(session, repo, "docs/supportedHashes.json"))}


def _torch_config_sha1(session, repo):
    # config.yml de Torch (Starship, Ghostship) : chaque version acceptee est une
    # cle de premier niveau = SHA-1 de la ROM. Lu par motif plutot que par un
    # parseur YAML (pas de dependance en plus) : seules ces cles commencent en
    # colonne 0 par 40 chiffres hexadecimaux.
    return set(re.findall(r"^([0-9a-f]{40}):", _github_file(session, repo, "config.yml"), re.MULTILINE))


def _readme_md5(session, repo):
    # README de fgsfdsfgs/perfect_dark : "... (md5 `e03b088b...`)" par version.
    return set(re.findall(r"md5 `([0-9a-f]{32})`", _github_file(session, repo, "README.md")))


def _twilight_princess(game):
    # README de DuskLight : tous les disques commerciaux de Twilight Princess,
    # GameCube et Wii, sauf la version Wii coreenne. Ecartes aussi : la demo Wii
    # et le disque de codes Action Replay (sans licence, nom different).
    name = game.get("name", "")
    return (re.match(r"(Legend of Zelda, The|Zelda no Densetsu) - Twilight Princess \(", name) is not None
            and not re.search(r"\((Korea|Demo)\)", name))


# (nom du dat produit, systeme RetroBat, sources, selection, empreinte comparee,
#  forcepacking ROMVault ou None, suffixe ajoute au nom des jeux par source ou
#  None, description)
#
# forcepacking "fileonly" pour les portages N64 : leur es_systems n'accepte que
# .z64/.n64, une ROM zippee par ROMVault n'apparaitrait plus dans RetroBat.
# DuskLight : rien a imposer, ses .iso Redump recoivent deja la regle "disque"
# de RBTools (fichiers non zippes, a plat).
SUBSETS = [
    ("Ship of Harkinian - Ocarina of Time", "soh", ("n64",),
     lambda s: _supported_hashes_json(s, "HarbourMasters/Shipwright"), "sha1", "fileonly", None,
     "Ocarina of Time ROMs supported by Ship of Harkinian (docs/supportedHashes.json)"),
    ("2 Ship 2 Harkinian - Majora's Mask", "2ship", ("n64",),
     lambda s: _supported_hashes_json(s, "HarbourMasters/2ship2harkinian"), "sha1", "fileonly", None,
     "Majora's Mask ROMs supported by 2 Ship 2 Harkinian (docs/supportedHashes.json)"),
    # US 1.0/1.1, Japon, Europe (Lylat Wars) et Chine (iQue) ; les versions
    # decompressees du config.yml ne sont pas des dumps et n'ont pas de dat.
    ("Starship - Star Fox 64", "starship", ("n64", "ique"),
     lambda s: _torch_config_sha1(s, "HarbourMasters/Starship"), "sha1", "fileonly", None,
     "Star Fox 64 ROMs supported by Starship (config.yml)"),
    ("Ghostship - Super Mario 64", "ghostship", ("n64",),
     lambda s: _torch_config_sha1(s, "HarbourMasters/Ghostship"), "sha1", "fileonly", None,
     "Super Mario 64 ROMs supported by Ghostship (config.yml)"),
    ("Perfect Dark - Port", "pdark", ("n64",),
     lambda s: _readme_md5(s, "fgsfdsfgs/perfect_dark"), "md5", "fileonly", None,
     "Perfect Dark ROMs supported by the fgsfdsfgs/perfect_dark port (README md5)"),
    # Meme nom Redump sur GameCube et Wii ("... Twilight Princess (USA)",
    # "... (Japan)") : deux jeux homonymes dans un meme dat se confondraient,
    # d'ou le suffixe de plateforme ajoute au nom du jeu et de son fichier.
    # DuskLight lit l'image elle-meme, le nom du fichier lui est indifferent.
    ("DuskLight - Twilight Princess", "dusklight", ("gamecube", "wii"),
     None, None, None, {"gamecube": " (GameCube)", "wii": " (Wii)"},
     "Twilight Princess discs supported by DuskLight (GameCube and Wii, without Korea, demo and Action Replay)"),
]


def _source_path(key):
    folder, prefix = SOURCES[key]
    candidates = [p for p in glob.glob(os.path.join(folder, glob.escape(prefix) + "*"))
                  if "(Parent-Clone)" not in p and p.lower().endswith((".dat", ".xml"))]
    # Trie sur la date en fin de nom ("(20260928-175532)", "(2026-06-13 18-14-01)"),
    # pas sur le nom entier : le nombre de jeux qui la precede change (Redump).
    return max(candidates, key=lambda p: re.sub(r"\D", "", p.rsplit("(", 1)[-1]), default=None)


def _day(version):
    """"20260928-175532" (No-Intro) ou "2026-06-13 18-14-01" (Redump) -> "2026-09-28"."""
    digits = re.sub(r"\D", "", version or "")[:8]
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}" if len(digits) == 8 else ""


def _renamed(game, suffix):
    game.set("name", game.get("name") + suffix)
    description = game.find("description")
    if description is not None and description.text:
        description.text += suffix
    for rom in game.iter("rom"):
        stem, ext = os.path.splitext(rom.get("name", ""))
        rom.set("name", stem + suffix + ext)
    return game


def build():
    session = retrying_session()
    parsed = {}

    def source(key):
        if key not in parsed:
            path = _source_path(key)
            if path is None:
                raise RuntimeError(f"Dat source absent : {SOURCES[key]}")
            parsed[key] = (path, ET.parse(path).getroot())
        return parsed[key]

    with replace_directory(OUTPUT_DIR) as out_dir:
        for name, system, keys, wanted, hash_kind, packing, suffixes, note in SUBSETS:
            wanted_hashes = wanted(session) if wanted else None
            if wanted is not None and not wanted_hashes:
                raise RuntimeError(f"{name} : liste des ROM acceptees vide ou illisible")

            games, found, used, versions = [], set(), [], []
            for key in keys:
                path, root = source(key)
                used.append(os.path.basename(path))
                header = root.find("header")
                versions.append(_day(header.findtext("version") if header is not None else ""))
                for game in root:
                    if game.tag not in ("game", "machine"):
                        continue
                    if wanted_hashes is None:
                        keep = _twilight_princess(game)
                    else:
                        hashes = {(r.get(hash_kind) or "").lower() for r in game.iter("rom")}
                        keep = bool(hashes & wanted_hashes)
                        found |= hashes & wanted_hashes
                    if not keep:
                        continue
                    game = copy.deepcopy(game)
                    # id/cloneofid (No-Intro), cloneof/romof : renvoient a des
                    # jeux qui ne sont pas dans ce sous-ensemble.
                    for attr in ("id", "cloneofid", "cloneof", "romof"):
                        game.attrib.pop(attr, None)
                    games.append(_renamed(game, suffixes[key]) if suffixes else game)

            if not games:
                raise RuntimeError(f"{name} : aucun jeu trouve dans {used}")

            out = ET.Element("datafile")
            out_header = ET.SubElement(out, "header")
            for tag, value in [
                ("name", name),
                ("description", note),
                # La plus recente des dates des dats sources : change quand l'un
                # d'eux change, reste stable sinon (pas de faux "mise a jour").
                ("date", max(versions)),
                ("author", "No-Intro" if keys[0] in ("n64", "ique") else "redump.org"),
                ("comment", f"Subset built by auto-datfile-generator (ports-subsets.py) for RetroBat's "
                            f"{system} system from {', '.join(used)}"),
            ]:
                if value:
                    ET.SubElement(out_header, tag).text = value
            if packing:
                ET.SubElement(out_header, "romvault", {"forcepacking": packing})

            out.extend(games)
            ET.indent(out, space="\t")
            out_path = os.path.join(out_dir, f"{name}.xml")
            with open(out_path, "w", encoding="utf-8", newline="\n") as f:
                f.write('<?xml version="1.0"?>\n')
                f.write(ET.tostring(out, encoding="unicode"))
                f.write("\n")

            print(f"{name} ({system}) : {len(games)} jeu(x) -> {out_path}")
            for game in games:
                print(f"  {game.get('name')}")
            if wanted_hashes is not None and wanted_hashes - found:
                print(f"  {len(wanted_hashes - found)} empreinte(s) acceptee(s) par le portage absente(s) des dats : "
                      + ", ".join(sorted(wanted_hashes - found)))


try:
    build()
except KeyboardInterrupt:
    pass
