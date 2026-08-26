import os
import re
import xml.etree.ElementTree as ET

# Partage entre retrobat-systems.py (rafraichissement quotidien) et
# retrobat-systems-discover.py (proposition de nouveaux candidats, a la
# demande) : le chargement des catalogues (manifestes + dossiers "loose")
# est identique dans les deux, seul ce qu'on en fait diverge.

# no-intro.py produit DEUX manifestes ("standard" et "parent-clone"), tous
# les deux publies dans le meme dossier "no-intro/" — n'indexer que
# no-intro_parent-clone.xml faisait rater tous les dats "standard" (ex.
# "Mobile - J2ME" sans le suffixe "(Parent-Clone)") lors du rafraichissement,
# constate en reel : 133 candidats "introuvables" a chaque run alors qu'ils
# existent bien sur disque.
MANIFESTS = {
    "No-Intro": ["no-intro.xml", "no-intro_parent-clone.xml"],
    "Redump": ["redump.xml"],
    "TOSEC": ["tosec.xml"],
}

# Fournisseurs sans manifeste externe : chaque fichier du dossier EST son
# propre dat (voir load_loose_folder) — le nom de fichier sert de nom de
# catalogue, pas une entree d'un manifeste partage.
LOOSE_FOLDERS = {
    "Clean CPC DB": "clean-cpc-db",
    "WHDLoad": "whdload",
    "Pleasuredome MAME": "pleasuredome-mame",
    "Pleasuredome HBMAME": "pleasuredome-hbmame",
    "Pleasuredome PinMAME": "pleasuredome-pinmame",
    "Visual Pinball": "visual-pinball",
    "Future Pinball": "future-pinball",
    "FBNeo": "fbneo",
    "Libretro-database": "libretro-database-dat",
    # eggmansworld-datfiles.py met les 19 collections a plat dans un seul
    # dossier (demande explicite de Cedric) : une seule source ici, comme
    # les autres, plutot qu'une par collection.
    "Eggmansworld - Datfiles": "Eggmansworld - Datfiles",
    # libretro-database-metadat.py garde un sous-dossier par categorie
    # (contrairement a Eggmansworld) : no-intro et tosec y partagent des
    # noms de fichiers identiques (ex. "Atari - 2600.dat"), un dossier plat
    # les ecraserait l'un l'autre.
    "Libretro-database (MAME-Split)": "libretro-database-metadat/mame-split",
    "Libretro-database (MAME)": "libretro-database-metadat/mame",
    "Libretro-database (No-Intro)": "libretro-database-metadat/no-intro",
    "Libretro-database (Redump)": "libretro-database-metadat/redump",
    "Libretro-database (TOSEC)": "libretro-database-metadat/tosec",
}

# Choix de Cedric : garder le nom de fichier court (ex. "sg1000",
# "samcoupe_cass"), meme quand l'en-tete Logiqx a une <description> plus
# parlante — mais ces dats individuels par driver n'ont ni date ni version
# dans leur nom de fichier (contrairement aux gros sets "MAME 0.289 ROMs
# (merged)..."), donc Version reste vide sans aller la lire dans l'en-tete
# a la place (voir _read_dat_header_version).
READ_XML_VERSION = {
    "Pleasuredome MAME",
    "Pleasuredome HBMAME",
    "Pleasuredome PinMAME",
}

# Les fournisseurs sans manifeste (load_loose_folder) embarquent souvent une
# date/version DANS le nom de fichier lui-meme (pas de <version> separee a
# lire) : No-Intro/Redump-style "(20251208-180029)", WHDLoad-style
# "(2026-08-24)", Eggmansworld-style "(2024-11-10_RomVault)". Sans ca, cette
# date polluait "Name" et "Version" restait vide. Ancre en fin de chaine
# uniquement : ne doit jamais toucher un qualificatif non-date comme
# "(Parent-Clone)" ou "(merged)", qui doit rester dans le nom.
_TRAILING_DATE_RE = re.compile(
    r"\s*\((\d{4}-\d{2}-\d{2}(?:_\w+)?|\d{8}-\d{6})\)\s*$"
)


def _split_trailing_date(name):
    match = _TRAILING_DATE_RE.search(name)
    if not match:
        return name, ""
    return name[:match.start()].strip(), match.group(1)


# Meme probleme, mais en tete de nom plutot qu'en fin : les dats
# Pleasuredome MAME/HBMAME/PinMAME embarquent le numero de version du
# romset dans le nom lui-meme, juste apres le nom du systeme — "MAME 0.289
# ROMs (merged)", "HBMAME 0.289.1 ROMs (bios-devices)", "PinMAME 3.6.0-1227
# ROMs (split)" (formats X.Y / X.Y.Z / X.Y.Z-build selon le systeme).
#
# Retire UNIQUEMENT le numero de version, garde le prefixe (MAME/HBMAME/
# PinMAME) dans le nom : le retirer aussi casse le rapprochement avec le
# systeme RetroBat correspondant (plus aucun token "mame"/"hbmame"/
# "pinmame" dans le nom => plus aucun candidat pour le systeme MAME
# lui-meme, constate en reel).
_LEADING_VERSION_RE = re.compile(
    r"^(MAME|HBMAME|PinMAME)\s+(\d+(?:\.\d+)+(?:-\d+)?)\s+(.+)$"
)


def _split_leading_version(name):
    match = _LEADING_VERSION_RE.match(name)
    if not match:
        return name, ""
    prefix, version, rest = match.group(1), match.group(2), match.group(3)
    return f"{prefix} {rest}".strip(), version


def load_manifest(path):
    if not os.path.exists(path):
        return []
    tree = ET.parse(path)
    entries = []
    for datfile in tree.getroot().findall("datfile"):
        entries.append({
            "name": datfile.findtext("name") or "",
            "version": datfile.findtext("version") or "",
            "url": datfile.findtext("url") or "",
            "file": datfile.findtext("file") or "",
        })
    return entries


def _read_dat_header_version(path):
    """Lit uniquement <header><date> (a defaut <header><version>), sans
    jamais parser le reste du fichier (liste des <machine>/<game>) —
    certains dats Pleasuredome font plusieurs dizaines de Mo une fois
    decompresses. iterparse est un parseur incremental : arreter la boucle
    (return) arrete aussi la lecture du fichier, pas de cout cache. Depth
    calque sur XmlReader.Depth (racine = 0, <header> = 1, <date>/<version> = 2).

    Prefere <date> a <version> : <version> ne fait souvent que refleter la
    version globale de MAME au moment de l'export (deja capturee par
    ailleurs pour les gros sets), <date> dit vraiment quand CE fichier a
    ete regenere."""
    depth = -1
    date_value = None
    version_value = None
    try:
        with open(path, "rb") as f:
            for event, elem in ET.iterparse(f, events=("start", "end")):
                if event == "start":
                    depth += 1
                    if depth == 1 and elem.tag != "header":
                        return None
                    continue

                if depth == 2 and elem.tag == "date":
                    date_value = (elem.text or "").strip() or None
                elif depth == 2 and elem.tag == "version":
                    version_value = (elem.text or "").strip() or None
                if depth == 1 and elem.tag == "header":
                    return date_value or version_value
                depth -= 1
    except ET.ParseError:
        return None
    return date_value or version_value


def load_loose_folder(folder, read_xml_version=False):
    """Pas de manifeste : chaque fichier .dat/.xml du dossier est lui-meme
    un catalogue a une seule entree — son nom de fichier (sans extension,
    sans date/version embarquee) sert de nom stable. Son URL brute est deja
    publiee par le script qui a rempli ce dossier plus tot dans le meme
    run. Pour les sources listees dans READ_XML_VERSION, si aucune
    date/version n'a pu etre extraite du nom lui-meme, on va la lire dans
    l'en-tete XML du fichier (voir _read_dat_header_version)."""
    if not os.path.isdir(folder):
        return []

    repo = os.environ.get("GITHUB_REPOSITORY", "goldorakiller/auto-datfile-generator")
    entries = []
    for filename in sorted(os.listdir(folder)):
        if not (filename.lower().endswith(".dat") or filename.lower().endswith(".xml")):
            continue

        name = os.path.splitext(filename)[0]

        name, version = _split_trailing_date(name)
        if not version:
            name, version = _split_leading_version(name)
        if not version and read_xml_version:
            version = _read_dat_header_version(os.path.join(folder, filename)) or ""

        entries.append({
            "name": name,
            "version": version,
            "url": f"https://raw.githubusercontent.com/{repo}/master/{folder}/{filename}",
            "file": filename,
        })
    return entries


def load_all_catalogs():
    """source -> liste d'entrees, pour tous les fournisseurs (manifestes +
    dossiers loose). Suppose que les scripts de mirroring ont deja tourne
    dans ce meme run (fichiers deja sur disque, pas de telechargement ici)."""
    catalogs = {}
    for source, filenames in MANIFESTS.items():
        entries = []
        for filename in filenames:
            entries.extend(load_manifest(filename))
        catalogs[source] = entries
        print(f"{source}: {len(entries)} entries ({', '.join(filenames)})")

    for source, folder in LOOSE_FOLDERS.items():
        entries = load_loose_folder(folder, source in READ_XML_VERSION)
        catalogs[source] = entries
        print(f"{source}: {len(entries)} entries ({folder}/)")

    return catalogs


def build_catalog_index(catalogs):
    """source -> {name: entry}, pour retrouver rapidement l'entree fraiche
    correspondant a un candidat deja publie (cle stable : Source+Name, sans
    date/version embarquee grace a load_loose_folder ci-dessus)."""
    return {
        source: {entry["name"]: entry for entry in entries}
        for source, entries in catalogs.items()
    }
