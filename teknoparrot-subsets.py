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
# telecharge a chaque run mais JAMAIS commite : seuls les sous-ensembles le
# sont.
#
# Chaque jeu de la collection porte le nom de son profil TeknoParrot
# (<GameProfile>Tekken6</GameProfile>) et sa carte dans son nom
# ("Tekken 6 (2007)[Namco System 357][TP]"). RetroBat exige un dossier de jeu
# NOMME D'APRES LE PROFIL, plus l'extension du systeme (wiki RetroBat :
# MKDX.teknoparrot) : le sous-ensemble renomme donc chaque jeu "<profil><ext>",
# pour que le Fix de ROMVault cree exactement le dossier attendu. Le nom
# d'Eggman est garde en description.
#
# forcepacking "fileonly" : TeknoParrot a besoin des dossiers tels quels,
# ROMVault ne doit jamais les zipper.
#
# Eggman demande de ne pas distribuer son dat sans son README et son
# changelog : l'en-tete du sous-ensemble renvoie vers la release d'origine.

RELEASES_API = "https://api.github.com/repos/Eggmansworld/TeknoParrot/releases/latest"
OUTPUT_DIR = "teknoparrot-subsets"
COLLECTION_DAT_PREFIX = "TeknoParrot Collection/TeknoParrot Collection ("

# (nom du dat produit, cartes gardees (texte entre crochets du nom), extension
#  des dossiers de jeu attendue par RetroBat, description)
SUBSETS = [
    ("TeknoParrot - Namco System 357-369", ("Namco System 357", "Namco System 369"), ".game",
     "Namco System 357 and 369 games for RetroBat's namco3xx system, folders named <GameProfile>.game"),
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


def build(local_zip=None):
    content, zip_name, release_url = _download_release_zip(local_zip)

    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        dat_name = next(n for n in zf.namelist() if n.startswith(COLLECTION_DAT_PREFIX) and n.lower().endswith(".dat"))
        print(f"Dat source : {dat_name}")

        kept = {name: [] for name, _, _, _ in SUBSETS}
        header = None
        # ~620 Mo : lecture en flux depuis le zip, chaque jeu non retenu est libere.
        with zf.open(dat_name) as f:
            for _, elem in ET.iterparse(f, events=("end",)):
                if elem.tag == "header":
                    header = elem
                    continue
                if elem.tag != "game":
                    continue

                board = _board_of(elem.get("name", ""))
                for subset, boards, ext, _ in SUBSETS:
                    if board in boards:
                        profile = (elem.findtext("GameProfile") or "").strip()
                        if not profile:
                            print(f"  IGNORE (pas de GameProfile) : {elem.get('name')}")
                            break
                        original = elem.get("name")
                        elem.set("name", profile + ext)
                        description = elem.find("description")
                        if description is None:
                            description = ET.SubElement(elem, "description")
                        description.text = original
                        kept[subset].append(elem)
                        break
                else:
                    elem.clear()

    with replace_directory(OUTPUT_DIR) as out_dir:
        for subset, boards, ext, note in SUBSETS:
            games = kept[subset]
            if not games:
                raise RuntimeError(f"{subset} : aucun jeu pour {boards}")

            names = [g.get("name") for g in games]
            duplicates = {n for n in names if names.count(n) > 1}
            if duplicates:
                raise RuntimeError(f"{subset} : plusieurs jeux pour le meme profil {sorted(duplicates)}")

            out = ET.Element("datafile")
            out_header = ET.SubElement(out, "header")
            for tag, value in [
                ("name", subset),
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
            path = os.path.join(out_dir, f"{subset}.xml")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write('<?xml version="1.0"?>\n')
                f.write(ET.tostring(out, encoding="unicode"))
                f.write("\n")

            size = sum(int(r.get("size") or 0) for g in games for r in g.iter("rom"))
            print(f"{subset} : {len(games)} jeu(x), {size / 1e9:.0f} Go, "
                  f"{os.path.getsize(path) / 1048576:.1f} Mo de dat -> {path}")


try:
    # Argument facultatif : chemin d'un zip deja telecharge (essai en local).
    build(sys.argv[1] if len(sys.argv) > 1 else None)
except KeyboardInterrupt:
    pass
