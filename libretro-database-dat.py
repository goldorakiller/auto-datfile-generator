import os

import requests

# Config — meme mecanique que fbneo.py : des .dat deja individuels a la
# racine du dossier "dat" du repo officiel libretro-database (~48 systemes
# non couverts par No-Intro/Redump/TOSEC : DOS, ScummVM, Quake, PICO-8,
# Amstrad CPC, GameCube, Wii, PS3...). Pas de zip a ouvrir. Le fichier
# "ps1.idlst" (pas un .dat) est ignore.
CONTENTS_API = "https://api.github.com/repos/libretro/libretro-database/contents/dat"
OUTPUT_DIR = "libretro-database-dat"


def build():
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
