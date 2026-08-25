import html
import os
import re
import zipfile
from io import BytesIO
from urllib.parse import unquote

import requests

from dat_output_dir import replace_directory

# Config — meme mecanique que pleasuredome-mame.py, dossier different sur le
# meme site. PinMAME n'a qu'un seul datfile publie (format "split"), pas de
# variantes merged/non-merged ni de version "Update" a exclure ici.
INDEX_URL = "https://pleasuredome.github.io/pleasuredome/nonmame/pinmame/index.html"
OUTPUT_DIR = "pleasuredome-pinmame"

_LINK_RE = re.compile(r'href="(https://github\.com/pleasuredome/pleasuredome/raw/gh-pages/nonmame/pinmame/[^"]+\.zip)"')


def find_zips():
    page = requests.get(INDEX_URL, timeout=150)
    page.raise_for_status()
    return [html.unescape(href) for href in _LINK_RE.findall(page.text)]


def build():
    urls = find_zips()
    print(f"{len(urls)} datfile(s) trouve(s)")

    # Meme raison que pleasuredome-mame.py : eviter que d'anciennes versions
    # de dats restent a cote des nouvelles, sans pour autant publier un
    # dossier vide/partiel si une panne reseau survient en cours de route.
    with replace_directory(OUTPUT_DIR) as out_dir:
        for url in urls:
            filename = unquote(url.rsplit("/", 1)[-1])
            print(f"Downloading {filename}")
            resp = requests.get(url, timeout=600)
            resp.raise_for_status()

            with zipfile.ZipFile(BytesIO(resp.content)) as archive:
                for name in archive.namelist():
                    if not name.lower().endswith(".xml"):
                        continue
                    data = archive.read(name)
                    out_name = os.path.basename(name)
                    with open(os.path.join(out_dir, out_name), "wb") as f:
                        f.write(data)
                    print(f"  -> {out_name} ({len(data)} bytes)")

    print("Finished")


try:
    build()
except KeyboardInterrupt:
    pass
