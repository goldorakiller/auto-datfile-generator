import os
import zipfile
from io import BytesIO

import requests

# Config — 19 collections independantes (verifie en reel aout 2026 : pcsx2x6,
# linuxloader, vic20ultimatetape, exo, ipodclickwheel, bluemaxima, rpgmaker,
# projectegg, digitoxin, pinballpc, touhou, sharpx68000, segaalldotnet,
# laserdisc, hvsc, goodtools, fruitmachines, c64ultimatetape,
# arcadeambience), chacune une release GitHub separee avec un zip
# "*_RomVault.zip" (parfois accompagne de README/Changelog/extras a
# ignorer). Parcourt l'API des releases au lieu de coder la liste en dur :
# suit automatiquement une 20e collection le jour ou Eggmansworld en ajoute
# une.
RELEASES_API = "https://api.github.com/repos/Eggmansworld/Datfiles/releases"

# Marge sous la limite git de 100 Mo/fichier (verifie en reel : le
# "Sega ALLS" de la collection segaalldotnet fait 421 Mo une fois extrait,
# bien au-dela — ces gros fichiers sont ignores plutot que de faire
# planter le push, comme pour TeknoParrot Collection (617 Mo, laisse de
# cote entierement) mais au cas par cas ici puisque le reste d'une meme
# collection peut tenir.
MAX_FILE_SIZE = 95 * 1024 * 1024


def find_romvault_zip(assets):
    for asset in assets:
        name = asset["name"]
        if name.lower().endswith(".zip") and "romvault" in name.lower():
            return asset
    return None


def build():
    resp = requests.get(RELEASES_API, params={"per_page": 100}, timeout=150)
    resp.raise_for_status()
    releases = resp.json()
    print(f"{len(releases)} collection(s) trouvee(s)")

    for release in releases:
        tag = release["tag_name"]
        asset = find_romvault_zip(release.get("assets", []))
        if asset is None:
            print(f"{tag} : aucun zip RomVault trouve, ignore")
            continue

        print(f"{tag} : telechargement {asset['name']}")
        file_resp = requests.get(asset["browser_download_url"], timeout=600)
        file_resp.raise_for_status()

        output_dir = os.path.join("eggmansworld-datfiles", tag)
        with zipfile.ZipFile(BytesIO(file_resp.content)) as archive:
            for name in archive.namelist():
                if not (name.lower().endswith(".dat") or name.lower().endswith(".xml")):
                    continue

                info = archive.getinfo(name)
                if info.file_size > MAX_FILE_SIZE:
                    print(f"  IGNORE (trop gros pour git, {info.file_size} bytes) : {name}")
                    continue

                os.makedirs(output_dir, exist_ok=True)
                data = archive.read(name)
                out_name = os.path.basename(name)
                with open(os.path.join(output_dir, out_name), "wb") as f:
                    f.write(data)
                print(f"  -> {out_name} ({len(data)} bytes)")

    print("Finished")


try:
    build()
except KeyboardInterrupt:
    pass
