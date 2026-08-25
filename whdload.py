import html
import os
import re
import shutil
import zipfile
from io import BytesIO

import requests

# Config
ROOT_URL = "https://ftp2.grandis.nu/turran/FTP/Retroplay%20WHDLoad%20Packs/"
OUTPUT_DIR = "whdload"

# Le dossier racine liste des sous-dossiers (les vraies archives .lha, classees
# par lettre — pas concernees) ET quelques zips a la racine, chacun contenant
# UN SEUL fichier .dat au format Logiqx standard (verifie en reel aout 2026 :
# meme forme que No-Intro/Redump). On ne prend QUE ces zips racine, jamais les
# sous-dossiers (des dizaines de milliers d'archives de jeux, pas notre role
# de les heberger).
_LINK_RE = re.compile(r'<a href="([^"]+\.zip)">')


def find_root_zips():
    page = requests.get(ROOT_URL, timeout=150)
    page.raise_for_status()
    return [html.unescape(href) for href in _LINK_RE.findall(page.text)]


def build():
    # Repart d'un dossier vide : si un pack racine change de nom/version
    # d'une fois sur l'autre, l'ancien fichier ne serait jamais ecrase sinon.
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    hrefs = find_root_zips()
    print(f"{len(hrefs)} zip(s) trouves a la racine")

    for href in hrefs:
        url = ROOT_URL + href
        print(f"Downloading {href}")
        resp = requests.get(url, timeout=150)
        resp.raise_for_status()

        with zipfile.ZipFile(BytesIO(resp.content)) as archive:
            for name in archive.namelist():
                if not name.lower().endswith(".dat"):
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
