from io import BytesIO
from time import sleep

import re
import xml.etree.ElementTree as ET
import zipfile

import requests


# Config
URL_HOME = 'http://redump.org/'
URL_DOWNLOADS = 'http://redump.org/downloads/'
regex = {
    'datfile': r'<a href="/datfile/(.*?)">',
    'date': r'\) \((.*?)\)\.',
    'name': r'filename="(.*?) Datfile',
    'filename': r'filename="(.*?)"',
}

XML_FILENAME = 'redump.xml'


def _find_dats():
    download_page = requests.get(URL_DOWNLOADS, timeout=30)
    download_page.raise_for_status()

    dat_files = re.findall(regex['datfile'], download_page.text)
    return dat_files


def Update_XML():
    dat_list = _find_dats()

    # zip file to store all DAT files
    zip_object = zipfile.ZipFile('redump.zip', 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9)

    # clrmamepro XML file
    tag_clrmamepro = ET.Element('clrmamepro')

    for dat in dat_list:
        print(f'Downloading {dat}')
        # section for this dat in the XML file
        tag_datfile = ET.SubElement(tag_clrmamepro, 'datfile')

        response = requests.get(URL_HOME+'datfile/'+dat, timeout=30)
        content_header = response.headers['Content-Disposition']

        # XML version
        dat_date = re.findall(regex['date'], content_header)[0]
        ET.SubElement(tag_datfile, 'version').text = dat_date

        # XML name & description
        temp_name = re.findall(regex['name'], content_header)[0]
        # trim the - from the end (if exists)
        if temp_name.endswith('-'):
            temp_name = temp_name[:-2]
        elif temp_name.endswith('BIOS'):
            temp_name = temp_name + ' Images'
        ET.SubElement(tag_datfile, 'name').text = temp_name
        ET.SubElement(tag_datfile, 'description').text = temp_name

        # URL tag in XML
        ET.SubElement(tag_datfile, 'url').text = 'https://github.com/dantob/auto-datfile-generator/releases/latest/download/redump.zip'

        # File tag in XML
        original_file_name = re.findall(regex['filename'], content_header)[0]
        new_file_name = f'{original_file_name[:-4]}.dat'
        ET.SubElement(tag_datfile, 'file').text = new_file_name

        # Author tag in XML
        ET.SubElement(tag_datfile, 'author').text = 'redump.org'

        # Command XML tag
        ET.SubElement(tag_datfile, 'comment').text = '_'

        # Get the DAT file
        datfile_name = f'{new_file_name[:-4]}.dat'
        print(f'DAT filename: {datfile_name}')
        if original_file_name.endswith('.zip'):
            # extract datfile from zip to store in the DB zip
            zipdata = BytesIO()
            zipdata.write(response.content)
            archive = zipfile.ZipFile(zipdata)
            zip_object.writestr(datfile_name, archive.read(datfile_name))
        else:
            # add datfile to DB zip file
            datfile = response.text
            zip_object.writestr(datfile_name, datfile)
        print()
        sleep(5)

    # store clrmamepro XML file
    xmldata = ET.tostring(tag_clrmamepro).decode()

    with open(XML_FILENAME, 'w', encoding="utf-8") as xmlfile:
        xmlfile.write(xmldata)

    print('Finished')


try:
    Update_XML()
except KeyboardInterrupt:
    pass
