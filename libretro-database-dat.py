import os

import requests

from dat_output_dir import replace_directory

# Config — meme mecanique que fbneo.py : des .dat deja individuels a la
# racine du dossier "dat" du repo officiel libretro-database (~48 systemes
# non couverts par No-Intro/Redump/TOSEC : DOS, ScummVM, Quake, PICO-8,
# Amstrad CPC, GameCube, Wii, PS3...). Pas de zip a ouvrir. Le fichier
# "ps1.idlst" (pas un .dat) est ignore.
CONTENTS_API = "https://api.github.com/repos/libretro/libretro-database/contents/dat"
OUTPUT_DIR = "libretro-database-dat"


def build():
    resp = requests.get(CONTENTS_API, timeout=150)
    resp.raise_for_status()
    entries = resp.json()

    dat_entries = [e for e in entries if e["name"].lower().endswith(".dat")]
    print(f"{len(dat_entries)} dat(s) trouve(s)")

    # Repart d'un dossier vide (si un fichier est renomme/retire en amont,
    # l'ancienne copie ne serait jamais nettoyee sinon), mais l'echange
    # avec le vrai dossier n'a lieu qu'a la fin en cas de succes complet.
    with replace_directory(OUTPUT_DIR) as out_dir:
        for entry in dat_entries:
            print(f"Downloading {entry['name']}")
            file_resp = requests.get(entry["download_url"], timeout=150)
            file_resp.raise_for_status()

            with open(os.path.join(out_dir, entry["name"]), "wb") as f:
                f.write(file_resp.content)
            print(f"  -> {len(file_resp.content)} bytes")

    print("Finished")


try:
    build()
except KeyboardInterrupt:
    pass
