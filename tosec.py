import os
import re
import zipfile
import xml.etree.ElementTree as ET

import requests

from dat_output_dir import replace_directory

# Config
DOWNLOADS_URL = "https://www.tosecdev.org/downloads"
SITE_ROOT     = "https://www.tosecdev.org"
ZIP_FILENAME  = "tosec.zip"
XML_FILENAME  = "tosec.xml"

regex = {
    "category" : r'<a href="(/downloads/category/\d+-(\d{4}-\d{2}-\d{2}))">\d{4}-\d{2}-\d{2}</a>',
    "download" : r'href="([^"]*\?download=[^"]+)"',
}


def _resolve_zip_url():
    """Le lien de release change a chaque publication TOSEC (~2x/an) : pas
    d'URL fixe ni de manifeste officiel, il faut lire la page /downloads."""
    downloads_page = requests.get(DOWNLOADS_URL, timeout=150)
    downloads_page.raise_for_status()

    category_match = re.search(regex["category"], downloads_page.text)
    if not category_match:
        raise RuntimeError("Could not find the latest TOSEC release category on the downloads page")
    category_url = SITE_ROOT + category_match.group(1)
    release_date = category_match.group(2)

    category_page = requests.get(category_url, timeout=150)
    category_page.raise_for_status()

    download_match = re.search(regex["download"], category_page.text)
    if not download_match:
        raise RuntimeError("Could not find the download link on the TOSEC release page")
    href = download_match.group(1)
    zip_url = href if href.startswith("http") else SITE_ROOT + href

    return zip_url, release_date


def update_XML():
    zip_url, release_date = _resolve_zip_url()
    print(f"Resolved TOSEC zip URL: {zip_url} (release {release_date})")

    print("Downloading TOSEC dat pack (large file, please wait) ...")
    response = requests.get(zip_url, timeout=600, stream=True)
    response.raise_for_status()

    with open(ZIP_FILENAME, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)

    repo = os.environ.get("GITHUB_REPOSITORY", "goldorakiller/auto-datfile-generator")

    # Dossier plat "tosec/" : une copie individuelle de chaque dat (a plat,
    # meme si le zip officiel a des sous-dossiers par categorie), pour que le
    # manifeste pointe directement dessus au lieu d'obliger a telecharger les
    # ~100 Mo du pack complet pour en extraire un seul fichier.
    individual_dir = "tosec"

    print("\nBuilding clrmamepro datfile ...\n")
    tag_clrmamepro = ET.Element("clrmamepro")

    # Repart d'un dossier vide a chaque release TOSEC (~2x/an) : si un dat
    # disparait ou change de nom entre deux releases, l'ancienne copie ne
    # serait jamais nettoyee sinon. L'echange avec le vrai dossier n'a lieu
    # qu'a la fin en cas de succes complet.
    with zipfile.ZipFile(ZIP_FILENAME, "r") as archive, replace_directory(individual_dir) as out_dir:
        for name in archive.namelist():
            if not name.lower().endswith(".dat"):
                continue

            # A plat : la seule partie qui compte cote consommateur (voir
            # RetroBat.Dat/Catalog/Sources/TosecZipSource.cs) est le nom de
            # fichier, jamais le chemin complet dans le zip.
            file_name = os.path.basename(name)
            print(file_name)
            display_name = file_name[:-4]  # sans l'extension .dat

            with archive.open(name) as entry, open(os.path.join(out_dir, file_name), "wb") as out:
                out.write(entry.read())

            tag_datfile = ET.SubElement(tag_clrmamepro, "datfile")
            # TOSEC ne date pas chaque dat individuellement (contrairement a
            # No-Intro) : la date de la release entiere sert de version, la
            # meme pour toutes les entrees de ce pack.
            ET.SubElement(tag_datfile, "version").text = release_date
            ET.SubElement(tag_datfile, "name").text = display_name
            ET.SubElement(tag_datfile, "description").text = display_name
            ET.SubElement(tag_datfile, "url").text = f"https://raw.githubusercontent.com/{repo}/master/{individual_dir}/{file_name}"
            ET.SubElement(tag_datfile, "file").text = file_name
            ET.SubElement(tag_datfile, "author").text = "TOSEC"
            ET.SubElement(tag_datfile, "comment").text = "_"

    xml_data = ET.tostring(tag_clrmamepro).decode()
    with open(XML_FILENAME, "w", encoding="utf-8") as xmlfile:
        xmlfile.write(xml_data)

    print("Finished")


try:
    update_XML()
except KeyboardInterrupt:
    pass
