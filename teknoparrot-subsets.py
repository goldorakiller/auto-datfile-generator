import gzip
import io
import os
import sys
import xml.etree.ElementTree as ET
import zipfile

from dat_output_dir import replace_directory
from http_session import github_api_headers, retrying_session

# Sous-ensembles de la "TeknoParrot Collection" d'Eggmansworld, fabriques ici.
#
# La collection vit dans un depot SEPARE (Eggmansworld/TeknoParrot, pas
# Eggmansworld/Datfiles que suit eggmansworld-datfiles.py), une release datee
# environ deux fois par semaine : zip de ~145 Mo contenant un dat de ~620 Mo,
# bien au-dela de la limite git de 100 Mo par fichier. Le zip est donc
# telecharge a chaque run mais JAMAIS commite.
#
# Chaque jeu de la collection porte le nom de son profil TeknoParrot
# (<GameProfile>Tekken6</GameProfile>) et sa carte dans son nom
# ("Tekken 6 (2007)[Namco System 357][TP]"). RetroBat exige un dossier de jeu
# NOMME D'APRES LE PROFIL, plus l'extension du systeme (wiki RetroBat :
# MKDX.teknoparrot) : chaque jeu est donc renomme "<profil><ext>", pour que le
# Fix de ROMVault cree exactement le dossier attendu. Le nom d'Eggman est garde
# en description.
#
# Un profil = un seul dossier possible dans RetroBat : quand plusieurs jeux de
# la collection partagent un profil (versions, regions : 14 jeux en trop au
# 28/09/2026), seul le PREMIER dans l'ordre d'Eggman (la version de
# base) est garde (choix de Cedric) ; les autres sont listes dans le journal.
#
# forcepacking "fileonly" : TeknoParrot a besoin des dossiers tels quels,
# ROMVault ne doit jamais les zipper.
#
# Eggman demande de ne pas distribuer son dat sans son README et son
# changelog : l'en-tete de chaque sous-ensemble renvoie vers la release.

RELEASES_API = "https://api.github.com/repos/Eggmansworld/TeknoParrot/releases/latest"
OUTPUT_DIR = "teknoparrot-subsets"
COLLECTION_DAT_PREFIX = "TeknoParrot Collection/TeknoParrot Collection ("

# (nom du dat produit, cartes gardees (texte entre crochets du nom) ou None =
#  toutes celles qu'aucun autre sous-ensemble ne prend, extension des dossiers
#  attendue par RetroBat, sortie, description)
# Sortie "repo" : fichier .xml commite dans teknoparrot-subsets/.
# Sortie "release" : fichier .datz (gzip, lu tel quel par ROMVault) a la racine,
# ignore par git et publie comme piece jointe de la release Daily_Rebuild :
# le dat complet fait ~150 Mo meme compresse, trop pour git (100 Mo/fichier),
# mais une piece jointe de release accepte jusqu'a 2 Go.
SUBSETS = [
    ("TeknoParrot - Namco System 357-369", ("Namco System 357", "Namco System 369"), ".game", "repo",
     "Namco System 357 and 369 games for RetroBat's namco3xx system, folders named <GameProfile>.game"),
    ("TeknoParrot-RetroBat", None, ".teknoparrot", "release",
     "All TeknoParrot games except Namco System 357/369 (namco3xx), for RetroBat's teknoparrot system, "
     "folders named <GameProfile>.teknoparrot, one game per profile"),
]


def _download_release_zip(local_zip=None):
    if local_zip:
        with open(local_zip, "rb") as f:
            return f.read(), os.path.basename(local_zip), "local"

    session = retrying_session()
    resp = session.get(RELEASES_API, headers=github_api_headers(), timeout=150)
    resp.raise_for_status()
    release = resp.json()
    asset = next(a for a in release["assets"] if a["name"].lower().endswith("_romvault.zip"))
    print(f"Release {release['tag_name']} : {asset['name']} ({asset['size'] / 1048576:.0f} Mo)")
    data = session.get(asset["browser_download_url"], timeout=600)
    data.raise_for_status()
    return data.content, asset["name"], release["html_url"]


def _board_of(name):
    # "Titre (version)(date)[Carte][TP]" : la carte est l'avant-dernier crochet.
    parts = [p.split("]")[0] for p in name.split("[")[1:]]
    return parts[-2] if len(parts) >= 2 else (parts[0] if parts else "")


def _subset_for(board):
    claimed = {b for _, boards, _, _, _ in SUBSETS if boards for b in boards}
    for subset in SUBSETS:
        boards = subset[1]
        if boards is not None and board in boards:
            return subset
        if boards is None and board not in claimed:
            return subset
    return None


def _write(games, header, subset, zip_name, release_url, path, compressed):
    name, _, _, _, note = subset
    out = ET.Element("datafile")
    out_header = ET.SubElement(out, "header")
    for tag, value in [
        ("name", name),
        ("description", note),
        ("category", header.findtext("category") if header is not None else ""),
        ("date", header.findtext("date") if header is not None else ""),
        ("author", header.findtext("author") if header is not None else ""),
        ("homepage", header.findtext("homepage") if header is not None else ""),
        ("url", header.findtext("url") if header is not None else ""),
        ("comment", f"Subset of {zip_name} built by auto-datfile-generator (teknoparrot-subsets.py). "
                    f"Eggman's README and changelog are part of the original release: {release_url}"),
    ]:
        if value:
            ET.SubElement(out_header, tag).text = value.strip()
    ET.SubElement(out_header, "romvault", {"forcepacking": "fileonly"})

    out.extend(games)
    ET.indent(out, space="\t")
    text = '<?xml version="1.0"?>\n' + ET.tostring(out, encoding="unicode") + "\n"
    if compressed:
        # mtime=0 : meme contenu = meme fichier, d'un run a l'autre.
        with open(path, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            gz.write(text.encode("utf-8"))
    else:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)


def build(local_zip=None):
    content, zip_name, release_url = _download_release_zip(local_zip)

    kept = {s[0]: [] for s in SUBSETS}
    first_owner = {s[0]: {} for s in SUBSETS}
    skipped = []
    header = None

    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        dat_name = next(n for n in zf.namelist() if n.startswith(COLLECTION_DAT_PREFIX) and n.lower().endswith(".dat"))
        print(f"Dat source : {dat_name}")

        # ~620 Mo : lecture en flux depuis le zip, chaque jeu non retenu est libere.
        with zf.open(dat_name) as f:
            for _, elem in ET.iterparse(f, events=("end",)):
                if elem.tag == "header":
                    header = elem
                    continue
                if elem.tag != "game":
                    continue

                original = elem.get("name", "")
                profile = (elem.findtext("GameProfile") or "").strip()
                subset = _subset_for(_board_of(original))
                if subset is None or not profile:
                    # README/changelog d'Eggman (pas de profil) ou carte non voulue.
                    elem.clear()
                    continue

                name, _, ext, _, _ = subset
                if profile in first_owner[name]:
                    skipped.append(f"{original}  (profil {profile} deja pris par {first_owner[name][profile]})")
                    elem.clear()
                    continue
                first_owner[name][profile] = original

                elem.set("name", profile + ext)
                description = elem.find("description")
                if description is None:
                    description = ET.SubElement(elem, "description")
                description.text = original
                kept[name].append(elem)

    if skipped:
        print(f"{len(skipped)} jeu(x) ecarte(s), profil deja utilise par un jeu precedent :")
        for line in skipped:
            print(f"  {line}")

    with replace_directory(OUTPUT_DIR) as out_dir:
        for subset in SUBSETS:
            name, boards, _, output, _ = subset
            games = kept[name]
            if not games:
                raise RuntimeError(f"{name} : aucun jeu pour {boards}")

            if output == "repo":
                path = os.path.join(out_dir, f"{name}.xml")
                _write(games, header, subset, zip_name, release_url, path, compressed=False)
            else:
                # A la racine (publie en piece jointe de release), via un fichier
                # temporaire : un echec en cours d'ecriture garde celui d'avant.
                path = f"{name}.datz"
                _write(games, header, subset, zip_name, release_url, path + ".tmp", compressed=True)
                os.replace(path + ".tmp", path)

            size = sum(int(r.get("size") or 0) for g in games for r in g.iter("rom"))
            print(f"{name} : {len(games)} jeu(x), {size / 1e9:.0f} Go, "
                  f"{os.path.getsize(path) / 1048576:.1f} Mo de dat -> {path}")


try:
    # Argument facultatif : chemin d'un zip deja telecharge (essai en local).
    build(sys.argv[1] if len(sys.argv) > 1 else None)
except KeyboardInterrupt:
    pass
