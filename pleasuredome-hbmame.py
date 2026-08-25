import html
import os
import re
import zipfile
from io import BytesIO
from urllib.parse import unquote

import requests

from dat_output_dir import replace_directory

# Config — meme mecanique que pleasuredome-mame.py, dossier different sur le
# meme site (HBMAME = homebrews MAME, romset plus petit).
INDEX_URL = "https://pleasuredome.github.io/pleasuredome/nonmame/hbmame/index.html"
OUTPUT_DIR = "pleasuredome-hbmame"

# "Update" (delta entre versions) exclu, seuls les sets complets comptent.
# Une entree de la page est un .7z ("MisfitMAME_HBMAME_ROMs.7z", une archive
# de dats individuels par jeu plutot qu'un dat unique) — hors de la forme
# geree ici (zip contenant un seul XML), volontairement ignoree pour l'instant.
_LINK_RE = re.compile(r'href="(https://github\.com/pleasuredome/pleasuredome/raw/gh-pages/nonmame/hbmame/[^"]+\.zip)"')


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
    urls = find_full_set_zips()
    print(f"{len(urls)} datfile(s) complet(s) trouve(s)")

    # Meme raison que pleasuredome-mame.py : le nom du dat embarque la
    # version (accumulerait sinon), mais l'echange avec le vrai dossier
    # n'a lieu qu'a la fin en cas de succes complet — une panne reseau en
    # cours de route laisse l'ancien mirror intact.
    with replace_directory(OUTPUT_DIR) as out_dir:
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
                    with open(os.path.join(out_dir, out_name), "wb") as f:
                        f.write(data)
                    print(f"  -> {out_name} ({len(data)} bytes)")

    print("Finished")


try:
    build()
except KeyboardInterrupt:
    pass
