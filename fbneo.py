import os
import shutil

import requests

# Config — le plus simple des mirrors : les .dat sont deja individuels a la
# racine du dossier "dats" du repo officiel FBNeo (libretro), un par systeme
# (Arcade, Neogeo, Megadrive, NES...). Pas de zip a ouvrir, juste lister puis
# telecharger chaque fichier tel quel.
CONTENTS_API = "https://api.github.com/repos/libretro/FBNeo/contents/dats"
OUTPUT_DIR = "fbneo"


def build():
    # Repart d'un dossier vide : si un fichier est renomme/retire en amont,
    # l'ancienne copie ne serait jamais nettoyee sinon.
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    resp = requests.get(CONTENTS_API, timeout=150)
    resp.raise_for_status()
    entries = resp.json()

    dat_entries = [e for e in entries if e["name"].lower().endswith(".dat")]
    print(f"{len(dat_entries)} dat(s) trouve(s)")

    for entry in dat_entries:
        print(f"Downloading {entry['name']}")
        file_resp = requests.get(entry["download_url"], timeout=150)
        file_resp.raise_for_status()

        with open(os.path.join(OUTPUT_DIR, entry["name"]), "wb") as f:
            f.write(file_resp.content)
        print(f"  -> {len(file_resp.content)} bytes")

    print("Finished")


try:
    build()
except KeyboardInterrupt:
    pass
