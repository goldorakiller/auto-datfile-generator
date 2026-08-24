import html
import os
import re
import zipfile
from io import BytesIO
from urllib.parse import unquote

import requests

# Config
INDEX_URL = "https://pleasuredome.github.io/pleasuredome/mame/index.html"
OUTPUT_DIR = "pleasuredome-mame"

# La page liste des datfiles complets (ROMs/CHDs/Software Lists/Extras,
# chacun un zip contenant un seul .xml MAME natif — verifie en reel aout
# 2026, ~8 Mo compresse / ~50 Mo decompresse pour le set ROMs non-merged) ET
# des liens magnet vers les vraies archives de ROMs/CHDs (torrents, jamais
# telecharges ici — pas notre role de les heberger, seulement les datfiles).
# Les sets "Update" (delta entre versions MAME) sont exclus : on ne veut que
# les sets complets.
_LINK_RE = re.compile(r'href="(https://github\.com/pleasuredome/pleasuredome/raw/gh-pages/mame/[^"]+\.zip)"')


def find_full_set_zips():
    page = requests.get(INDEX_URL, timeout=150)
    page.raise_for_status()

    urls = []
    for href in _LINK_RE.findall(page.text):
        url = html.unescape(href)
        filename = unquote(url.rsplit("/", 1)[-1])
        if "update" in filename.lower():
            continue
        urls.append(url)
    return urls


def build():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    urls = find_full_set_zips()
    print(f"{len(urls)} datfile(s) complet(s) trouve(s)")

    for url in urls:
        filename = unquote(url.rsplit("/", 1)[-1])
        print(f"Downloading {filename}")
        resp = requests.get(url, timeout=600)
        resp.raise_for_status()

        with zipfile.ZipFile(BytesIO(resp.content)) as archive:
            for name in archive.namelist():
                if not (name.lower().endswith(".xml") or name.lower().endswith(".dat")):
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
