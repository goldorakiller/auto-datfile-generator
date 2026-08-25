import html
import os
import re
import shutil
import zipfile
from io import BytesIO
from urllib.parse import unquote

import requests

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
    # Meme raison que pleasuredome-mame.py : eviter que d'anciennes versions
    # de dats restent a cote des nouvelles.
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    urls = find_zips()
    print(f"{len(urls)} datfile(s) trouve(s)")

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
                with open(os.path.join(OUTPUT_DIR, out_name), "wb") as f:
                    f.write(data)
                print(f"  -> {out_name} ({len(data)} bytes)")

    print("Finished")


try:
    build()
except KeyboardInterrupt:
    pass
