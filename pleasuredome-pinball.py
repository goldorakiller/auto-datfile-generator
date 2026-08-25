import os
import re
import zipfile
from contextlib import ExitStack
from io import BytesIO

import requests

from dat_output_dir import replace_directory

# Config — meme site que MAME/HBMAME, mais chaque datfile va dans SON PROPRE
# dossier (demande explicite : "un dossier Visual Pinball et un dossier
# Future Pinball"), pas un dossier "pinball" commun. Chaque zip contient
# PLUSIEURS xml (un par categorie de table : Original/Recreated/PinMame/VR/
# PuP-Pack..., verifie en reel aout 2026 : 132 fichiers pour Visual Pinball,
# 7 pour Future Pinball) — tous extraits a plat dans le dossier du systeme.
INDEX_URL = "https://pleasuredome.github.io/pleasuredome/nonmame/pinball/index.html"

TARGETS = {
    "Visual Pinball": "visual-pinball",
    "Future Pinball": "future-pinball",
}

_LINK_RE = re.compile(r'href="(https://github\.com/pleasuredome/pleasuredome/raw/gh-pages/nonmame/pinball/[^"]+\.zip)"')


def find_zips():
    page = requests.get(INDEX_URL, timeout=150)
    page.raise_for_status()
    return _LINK_RE.findall(page.text)


def build():
    urls = find_zips()
    print(f"{len(urls)} zip(s) trouve(s) sur la page")

    # Meme raison que pleasuredome-mame.py : eviter que d'anciennes versions
    # de dats restent a cote des nouvelles, sans pour autant publier un
    # dossier vide/partiel si une panne reseau survient en cours de route.
    # Les deux dossiers (Visual Pinball / Future Pinball) sont alimentes
    # dans la meme boucle, donc les deux echanges n'ont lieu qu'a la toute
    # fin, ensemble.
    with ExitStack() as stack:
        out_dirs = {
            folder: stack.enter_context(replace_directory(folder))
            for folder in TARGETS.values()
        }

        for url in urls:
            filename = url.rsplit("/", 1)[-1]
            output_dir = None
            for prefix, folder in TARGETS.items():
                if filename.startswith(prefix):
                    output_dir = out_dirs[folder]
                    break

            if output_dir is None:
                print(f"Ignore (systeme non reconnu) : {filename}")
                continue

            print(f"Downloading {filename} -> {output_dir}/")
            resp = requests.get(url, timeout=600)
            resp.raise_for_status()

            with zipfile.ZipFile(BytesIO(resp.content)) as archive:
                for name in archive.namelist():
                    if not name.lower().endswith(".xml"):
                        continue
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
