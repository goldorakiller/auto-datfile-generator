import os

import requests

from dat_output_dir import replace_directory

# Config — meme mecanique que libretro-database-dat.py, mais sur le dossier
# "metadat" du meme repo (contenu different : dats par mainteneur MAME et
# copies No-Intro/Redump/TOSEC maintenues par libretro plutot que les
# sources officielles). Un sous-dossier par categorie, PAS un dossier plat :
# no-intro et tosec partagent des noms de fichiers identiques (ex.
# "Atari - 2600.dat"), un dossier plat ecraserait l'un avec l'autre.
CONTENTS_API = "https://api.github.com/repos/libretro/libretro-database/contents/metadat"
OUTPUT_DIR = "libretro-database-metadat"

TARGETS = ["mame-split", "mame", "no-intro", "redump", "tosec"]

# Marge sous la limite git de 100 Mo/fichier (meme convention que
# eggmansworld-datfiles.py). Concretement, seul "MAME 2015 XML.zip" (dans
# metadat/mame) depasse une fois extrait (166 Mo) : ignore plutot que de
# faire planter le push.
MAX_FILE_SIZE = 95 * 1024 * 1024


def build():
    for category in TARGETS:
        resp = requests.get(f"{CONTENTS_API}/{category}", timeout=150)
        resp.raise_for_status()
        entries = resp.json()

        dat_entries = [
            e for e in entries
            if e["name"].lower().endswith(".dat") or e["name"].lower().endswith(".xml")
        ]
        print(f"{category} : {len(dat_entries)} dat(s) trouve(s)")

        # Repart d'un dossier vide (si un fichier est renomme/retire en
        # amont, l'ancienne copie ne serait jamais nettoyee sinon), mais
        # l'echange avec le vrai dossier n'a lieu qu'a la fin en cas de
        # succes complet pour cette categorie.
        with replace_directory(os.path.join(OUTPUT_DIR, category)) as out_dir:
            for entry in dat_entries:
                if entry["size"] > MAX_FILE_SIZE:
                    print(f"  IGNORE (trop gros pour git, {entry['size']} bytes) : {entry['name']}")
                    continue

                print(f"  Downloading {entry['name']}")
                file_resp = requests.get(entry["download_url"], timeout=150)
                file_resp.raise_for_status()

                with open(os.path.join(out_dir, entry["name"]), "wb") as f:
                    f.write(file_resp.content)
                print(f"    -> {len(file_resp.content)} bytes")

    print("Finished")


try:
    build()
except KeyboardInterrupt:
    pass
