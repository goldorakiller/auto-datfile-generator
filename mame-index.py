import io
import json
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone

from http_session import github_api_headers, retrying_session

# Index COMPACT des machines MAME, pour le filtre "MAME / Arcade" de RBTools (filtrer
# comme RomLister : genre, controles, joueurs, ecran, annee). Publie en piece jointe de
# la release (mame-index.json, ignore par git), jamais dans un DAT.
#
# Les DAT MAME de Pleasuredome (ceux que RBTools filtre) n'ont que nom/description/annee/
# fabricant et les flags bios/device/mecanique/runnable : ni controles, ni ecran, ni etat
# du pilote, ni lien parent/clone (verifie le 02/10/2026 : 0 <driver>, 0 cloneof sur
# 44 166 machines). Trois sources, toutes telechargees a chaque run :
# - liste XML OFFICIELLE de MAME (release GitHub mamedev/mame, mameXXXXlx.zip, ~20 Mo,
#   327 Mo decompresse, lue en flux) : cloneof, flags, pilote, annee, fabricant, joueurs,
#   boutons, controles, orientation, type d'ecran ;
# - catver.ini de Progetto-SNAPS (AntoPISA/MAME_SupportFiles, (c) AntoPISA) : genre
#   "Principal / Sous-genre" et mention " * Mature *" ;
# - nplayers.ini (nplayers.arcadebelgium.be, CC BY-SA 3.0) : "2P sim", "2P alt"...
# - languages.ini et bestgames.ini de Progetto-SNAPS (meme depot que catver) : langue(s)
#   du jeu et note par tranches de 10 (filtres "Languages" et "Rating" de RBTools, 19/11/2026).
# Une source injoignable : l'index n'est pas reecrit (piece jointe de la veille gardee).

OUTPUT_FILE = "mame-index.json"
MAME_RELEASE_API = "https://api.github.com/repos/mamedev/mame/releases/latest"
CATVER_URL = "https://raw.githubusercontent.com/AntoPISA/MAME_SupportFiles/main/catver.ini/catver.ini"
LANGUAGES_URL = "https://raw.githubusercontent.com/AntoPISA/MAME_SupportFiles/main/languages.ini/languages.ini"
BESTGAMES_URL = "https://raw.githubusercontent.com/AntoPISA/MAME_SupportFiles/main/bestgames.ini/bestgames.ini"
NPLAYERS_PAGE = "http://nplayers.arcadebelgium.be/"

# Ordre des colonnes de chaque machine (tableau, pour un fichier compact).
# Colonnes ajoutees TOUJOURS EN FIN : RBTools lit les colonnes par leur nom ("fields"), une
# version plus ancienne ignore simplement celles qu'elle ne connait pas.
FIELDS = ["cloneof", "flags", "driver", "year", "manufacturer", "players", "buttons",
          "controls", "orientation", "screens", "genre", "mature", "nplayers",
          "languages", "rating"]
FLAG_BIOS, FLAG_DEVICE, FLAG_MECHANICAL, FLAG_NOT_RUNNABLE = 1, 2, 4, 8
# Ajoutes le 19/11/2026 (memes raisons : une ancienne version de RBTools ne lit que 1/2/4/8) :
# - COCKTAIL : reglage "Cabinet" avec une valeur "Cocktail..." (retournement d'ecran pour une
#   table cocktail), SAUF si <driver cocktail="preliminary"> (retournement mal emule) ;
# - SAMPLES : besoin de fichiers samples (attribut sampleof) ;
# - ARTWORK : <driver requiresartwork="yes"> (decor/caches indispensables pour jouer) ;
# - NO_SOUND : <feature type="sound" status="unemulated"> (son non emule ; une machine
#   SANS materiel son, nosoundhardware="yes", n'est PAS concernee).
FLAG_COCKTAIL, FLAG_SAMPLES, FLAG_ARTWORK, FLAG_NO_SOUND = 16, 32, 64, 128


def control_code(element):
    """Type de controle MAME ramene a un code stable pour RBTools (None = boutons seuls)."""
    kind = element.get("type", "")
    ways = element.get("ways", "")
    if kind == "joy":
        if ways in ("4", "3 (half4)"):
            return "joy4"
        if ways in ("8", "16", "5 (half8)"):
            return "joy8"
        return "joy2"  # 2, vertical2, 1, strange2
    return {
        "only_buttons": None,
        "doublejoy": "doublejoy", "triplejoy": "doublejoy",
        "mouse": "trackball", "trackball": "trackball",
        "mahjong": "mahjong", "hanafuda": "mahjong",
        "keyboard": "keyboard", "keypad": "keyboard",
    }.get(kind, kind)  # stick, dial, paddle, pedal, lightgun, positional, gambling


def read_listxml(session):
    release = session.get(MAME_RELEASE_API, headers=github_api_headers(), timeout=150)
    release.raise_for_status()
    release = release.json()
    asset = next(a for a in release["assets"] if re.fullmatch(r"mame\d+lx\.zip", a["name"]))
    print(f"MAME {release['tag_name']} : {asset['name']} ({asset['size']:,} octets)")
    data = session.get(asset["browser_download_url"], timeout=600)
    data.raise_for_status()

    machines = {}
    version = ""
    with zipfile.ZipFile(io.BytesIO(data.content)) as archive:
        with archive.open(archive.namelist()[0]) as xml:
            for event, elem in ET.iterparse(xml, events=("start", "end")):
                if event == "start":
                    if elem.tag == "mame":
                        version = elem.get("build", "").split(" ")[0]
                    continue
                if elem.tag != "machine":
                    continue
                flags = 0
                flags |= FLAG_BIOS if elem.get("isbios") == "yes" else 0
                flags |= FLAG_DEVICE if elem.get("isdevice") == "yes" else 0
                flags |= FLAG_MECHANICAL if elem.get("ismechanical") == "yes" else 0
                flags |= FLAG_NOT_RUNNABLE if elem.get("runnable") == "no" else 0
                driver = elem.find("driver")
                if driver is not None:
                    flags |= FLAG_ARTWORK if driver.get("requiresartwork") == "yes" else 0
                    cocktail_ok = driver.get("cocktail") != "preliminary"
                else:
                    cocktail_ok = True
                # "Cabinet" est un interrupteur DIP (<dipswitch>/<dipvalue> : galaga, 1942) OU un
                # reglage de configuration (<configuration>/<confsetting> : pacman, invaders).
                if cocktail_ok and any(
                        setting.get("name", "").lower() == "cabinet" and
                        any(v.get("name", "").lower().startswith("cocktail")
                            for v in setting.findall("dipvalue") + setting.findall("confsetting"))
                        for setting in elem.findall("dipswitch") + elem.findall("configuration")):
                    flags |= FLAG_COCKTAIL
                flags |= FLAG_SAMPLES if elem.get("sampleof") else 0
                if any(f.get("type") == "sound" and f.get("status") == "unemulated" for f in elem.findall("feature")):
                    flags |= FLAG_NO_SOUND
                inp = elem.find("input")
                controls, buttons = set(), 0
                if inp is not None:
                    for control in inp.findall("control"):
                        code = control_code(control)
                        if code:
                            controls.add(code)
                        buttons = max(buttons, int(control.get("buttons", "0") or 0))
                displays = elem.findall("display")
                orientation = ""
                if displays:
                    orientation = "V" if displays[0].get("rotate") in ("90", "270") else "H"
                machines[elem.get("name")] = [
                    elem.get("cloneof", ""),
                    flags,
                    (driver.get("status", "")[:1] if driver is not None else ""),
                    elem.findtext("year", "") or "",
                    elem.findtext("manufacturer", "") or "",
                    int(inp.get("players", "0") or 0) if inp is not None else 0,
                    buttons,
                    sorted(controls),
                    orientation,
                    sorted({d.get("type", "") for d in displays if d.get("type")}),
                    "", 0, "",
                    [], 0,
                ]
                elem.clear()  # flux : 327 Mo de XML sans tout garder en memoire
    return version or release["tag_name"], machines


def read_ini_section(text, section):
    """Lignes cle=valeur d'une section [section] d'un .ini (catver, nplayers)."""
    values, current = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1]
            continue
        if current == section and "=" in line and not line.startswith(";"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def ini_version(text):
    match = re.search(r";;\s*\S+\s+(\d+\.\d+)", text)
    return match.group(1) if match else ""


def read_catver(session):
    resp = session.get(CATVER_URL, timeout=150)
    resp.raise_for_status()
    text = resp.content.decode("utf-8", errors="replace")
    return ini_version(text), read_ini_section(text, "Category")


def read_sections(text):
    """Toutes les sections d'un .ini "dossiers" de Progetto-SNAPS : nom de jeu -> [sections]."""
    result, current = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1]
            continue
        if not line or line.startswith(";") or current in (None, "FOLDER_SETTINGS", "ROOT_FOLDER"):
            continue
        result.setdefault(line, []).append(current)
    return result


def read_languages(session):
    resp = session.get(LANGUAGES_URL, timeout=150)
    resp.raise_for_status()
    text = resp.content.decode("utf-8", errors="replace")
    return ini_version(text), read_sections(text)


def read_bestgames(session):
    """Note = borne basse de la tranche ("70 to 80 (Good)" -> 70) ; un jeu non note n'est pas liste."""
    resp = session.get(BESTGAMES_URL, timeout=150)
    resp.raise_for_status()
    text = resp.content.decode("utf-8", errors="replace")
    ratings = {}
    for name, sections in read_sections(text).items():
        match = re.match(r"(\d+)\s+to\s+\d+", sections[0])
        if match:
            ratings[name] = int(match.group(1))
    return ini_version(text), ratings


def read_nplayers(session):
    page = session.get(NPLAYERS_PAGE, timeout=150)
    page.raise_for_status()
    links = re.findall(r'href="([^"]*nplayers(\d+)\.zip)"', page.text)
    url, number = max(links, key=lambda link: int(link[1]))
    resp = session.get(url, timeout=150)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as archive:
        text = archive.read("nplayers.ini").decode("utf-8", errors="replace")
    return f"0.{int(number)}", read_ini_section(text, "NPlayers")


def build():
    session = retrying_session()
    version, machines = read_listxml(session)
    catver_version, categories = read_catver(session)
    nplayers_version, nplayers = read_nplayers(session)
    languages_version, languages = read_languages(session)
    bestgames_version, ratings = read_bestgames(session)

    mature_mark = "* Mature *"
    for name, row in machines.items():
        genre = categories.get(name, "")
        if mature_mark in genre:
            row[11] = 1
            genre = genre.replace(mature_mark, "").strip()
        row[10] = genre
        row[12] = nplayers.get(name, "").strip()
        row[13] = sorted(set(languages.get(name, [])))
        row[14] = ratings.get(name, 0)

    index = {
        "mame": version,
        "catver": catver_version,
        "nplayers": nplayers_version,
        "languages": languages_version,
        "bestgames": bestgames_version,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": {
            "mame": "MAME listxml (mamedev/mame releases), MAME (c) MAMEdev and contributors",
            "catver": "catver.ini, progetto-SNAPS (c) AntoPISA, https://www.progettosnaps.net",
            "nplayers": "nplayers.ini, http://nplayers.arcadebelgium.be, CC BY-SA 3.0",
            "languages": "languages.ini, progetto-SNAPS (c) AntoPISA, https://www.progettosnaps.net",
            "bestgames": "bestgames.ini, progetto-SNAPS (c) AntoPISA, https://www.progettosnaps.net",
        },
        "fields": FIELDS,
        "machines": machines,
    }
    tmp = OUTPUT_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, OUTPUT_FILE)

    with_genre = sum(1 for r in machines.values() if r[10])
    with_np = sum(1 for r in machines.values() if r[12])
    print(f"{len(machines)} machines (catver {catver_version} : {with_genre}, nplayers {nplayers_version} : {with_np})")
    print(f"languages {languages_version} : {sum(1 for r in machines.values() if r[13])}, "
          f"bestgames {bestgames_version} : {sum(1 for r in machines.values() if r[14])}, "
          f"cocktail {sum(1 for r in machines.values() if r[1] & FLAG_COCKTAIL)}, "
          f"samples {sum(1 for r in machines.values() if r[1] & FLAG_SAMPLES)}, "
          f"artwork {sum(1 for r in machines.values() if r[1] & FLAG_ARTWORK)}, "
          f"son non emule {sum(1 for r in machines.values() if r[1] & FLAG_NO_SOUND)}")
    print(f"{OUTPUT_FILE} : {os.path.getsize(OUTPUT_FILE):,} octets")


try:
    build()
except KeyboardInterrupt:
    pass
