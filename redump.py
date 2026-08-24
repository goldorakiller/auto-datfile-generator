import os
import re
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from time import sleep

import requests

# Config
URL_HOME      = "http://redump.org/"
URL_DOWNLOADS = "http://redump.org/downloads/"
XML_FILENAME  = "redump.xml"
INDIVIDUAL_DIR = "redump"
REPO          = os.environ.get("GITHUB_REPOSITORY", "goldorakiller/auto-datfile-generator")

regex = {
    "datfile"  : r'<a href="/datfile/(.*?)">',
    "date"     : r"\) \((.*?)\)\.",
    "name"     : r'filename="(.*?) Datfile',
    "filename" : r'filename="(.*?)"',
}


def _find_dats():
    download_page = requests.get(URL_DOWNLOADS, timeout=150)
    download_page.raise_for_status()

    dat_files = re.findall(regex["datfile"], download_page.text)
    return dat_files


def update_XML():
    dat_list = _find_dats()

    # zip file to store all DAT files
    zip_object = zipfile.ZipFile("redump.zip", "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9)

    # Dossier plat "redump/" : une copie individuelle de chaque dat, pour que
    # le manifeste pointe directement dessus (raw.githubusercontent.com) au
    # lieu d'obliger a telecharger tout le zip partage pour en extraire un seul.
    os.makedirs(INDIVIDUAL_DIR, exist_ok=True)

    # clrmamepro XML file
    tag_clrmamepro = ET.Element("clrmamepro")

    for dat in dat_list:
        print(f"Downloading {dat}")
        # section for this dat in the XML file
        tag_datfile = ET.SubElement(tag_clrmamepro, "datfile")

        response = requests.get(URL_HOME + "datfile/" + dat, timeout=150)
        content_header = response.headers["Content-Disposition"]

        # XML version
        dat_date = re.findall(regex["date"], content_header)[0]
        ET.SubElement(tag_datfile, "version").text = dat_date

        # XML name & description
        temp_name = re.findall(regex["name"], content_header)[0]
        # trim the - from the end (if exists)
        if temp_name.endswith("-"):
            temp_name = temp_name[:-2]
        elif temp_name.endswith("BIOS"):
            temp_name = temp_name + " Images"
        ET.SubElement(tag_datfile, "name").text = temp_name
        ET.SubElement(tag_datfile, "description").text = temp_name

        # File tag in XML
        original_filename = re.findall(regex["filename"], content_header)[0]
        filename = f"{original_filename[:-4]}.dat"
        ET.SubElement(tag_datfile, "file").text = filename

        # URL tag in XML : le fichier individuel directement (redump/<file>),
        # pas le zip partage — evite tout telechargement+extraction cote client.
        ET.SubElement(tag_datfile, "url").text = f"https://raw.githubusercontent.com/{REPO}/master/{INDIVIDUAL_DIR}/{filename}"

        # Author tag in XML
        ET.SubElement(tag_datfile, "author").text = "redump.org"

        # Command XML tag
        ET.SubElement(tag_datfile, "comment").text = "_"

        # Get the DAT file
        datfile_name = f"{filename[:-4]}.dat"
        print(f"DAT filename: {datfile_name}")
        if original_filename.endswith(".zip"):
            # extract datfile from zip to store in the DB zip
            zipdata = BytesIO()
            zipdata.write(response.content)
            archive = zipfile.ZipFile(zipdata)
            datfile_bytes = archive.read(datfile_name)
            zip_object.writestr(datfile_name, datfile_bytes)
        else:
            # add datfile to DB zip file
            datfile_bytes = response.content
            zip_object.writestr(datfile_name, datfile_bytes)

        with open(os.path.join(INDIVIDUAL_DIR, datfile_name), "wb") as individual_file:
            individual_file.write(datfile_bytes)

        print()
        sleep(5)

    # store clrmamepro XML file
    xmldata = ET.tostring(tag_clrmamepro).decode()

    with open(XML_FILENAME, "w", encoding="utf-8") as xmlfile:
        xmlfile.write(xmldata)

    print("Finished")


try:
    update_XML()
except KeyboardInterrupt:
    pass
