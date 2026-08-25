import os
import re
import shutil
import zipfile
from io import BytesIO

import requests

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
    # Meme raison que pleasuredome-mame.py : eviter que d'anciennes versions
    # de dats restent a cote des nouvelles.
    for folder in TARGETS.values():
        shutil.rmtree(folder, ignore_errors=True)

    urls = find_zips()
    print(f"{len(urls)} zip(s) trouve(s) sur la page")

    for url in urls:
        filename = url.rsplit("/", 1)[-1]
        output_dir = None
        for prefix, folder in TARGETS.items():
            if filename.startswith(prefix):
                output_dir = folder
                break

        if output_dir is None:
            print(f"Ignore (systeme non reconnu) : {filename}")
            continue

        os.makedirs(output_dir, exist_ok=True)
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
