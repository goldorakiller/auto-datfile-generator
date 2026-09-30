import html
import os
import re
import zipfile
from io import BytesIO

from dat_output_dir import replace_directory
from http_session import retrying_session

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


def find_root_zips(session):
    page = session.get(ROOT_URL, timeout=150)
    page.raise_for_status()
    # La page cite chaque zip DEUX fois (verifie le 30/09/2026) : sans ce
    # dedoublonnage, chaque fichier etait telecharge deux fois, ce qui doublait
    # les chances de tomber sur une coupure de ce site. dict.fromkeys garde l'ordre.
    return list(dict.fromkeys(html.unescape(href) for href in _LINK_RE.findall(page.text)))


def build():
    session = retrying_session()
    hrefs = find_root_zips(session)
    print(f"{len(hrefs)} zip(s) trouves a la racine")

    # Repart d'un dossier vide (si un pack racine change de nom/version,
    # l'ancien fichier ne serait jamais ecrase sinon), mais l'echange avec
    # le vrai dossier n'a lieu qu'a la fin en cas de succes complet — une
    # panne reseau transitoire (deja vue plusieurs fois sur ce site) laisse
    # l'ancien mirror intact au lieu de publier un dossier vide.
    with replace_directory(OUTPUT_DIR) as out_dir:
        for href in hrefs:
            url = ROOT_URL + href
            print(f"Downloading {href}")
            resp = session.get(url, timeout=150)
            resp.raise_for_status()

            with zipfile.ZipFile(BytesIO(resp.content)) as archive:
                for name in archive.namelist():
                    if not name.lower().endswith(".dat"):
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
