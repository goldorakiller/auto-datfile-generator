"""DAT des jeux GOG INSTALLES (Windows), a partir des manifestes publics de GOG Galaxy.

Prototype (30/09/2026). Pourquoi cette source :
- les MD5 des installateurs hors ligne (setup_*.exe) ne sont donnes par GOG qu'aux
  comptes connectes : aucune base publique ne les contient ;
- en revanche, chaque version publiee d'un jeu ("build" de 2e generation) decrit les
  fichiers du jeu INSTALLE (chemin, taille, MD5), sur le CDN public de GOG, sans compte.
Le DAT verifie donc un dossier de jeu installe (par GOG Galaxy ou par l'installateur
hors ligne), jamais les fichiers setup_*.exe. A utiliser en VERIFICATION seule dans
ROMVault : un jeu installe modifie ses fichiers de configuration, un "Fix" les remplacerait.

Un DAT par langue ("GOG - Windows (English)", "GOG - Windows (French)") : un jeu du DAT
= un dossier sur le disque (installDirectory de GOG), le meme quelle que soit la langue
installee ; chaque DAT = fichiers communs ('*') + ceux de sa langue.

Catalogue : identifiants et titres de GOG Database (gogdb.org, donnees ouvertes).
"""
import argparse
import json
import os
import random
import time
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from xml.sax.saxutils import escape, quoteattr

from http_session import retrying_session

GOGDB = "https://www.gogdb.org/data"
META_CDN = "https://gog-cdn-fastly.gog.com/content-system/v2/meta/"
LANGUAGES = {"en-US": "English", "fr-FR": "French"}

_session = retrying_session()
_stats = {"requests": 0}


def _get(url):
    _stats["requests"] += 1
    resp = _session.get(url, timeout=150)
    resp.raise_for_status()
    return resp


def _meta(url):
    # Les meta et manifestes v2 sont du JSON compresse zlib (pas un Content-Encoding HTTP).
    # Certains vieux builds pointent vers un ancien CDN qui ne se resout plus
    # (gog-cdn-lumen.secure2.footprint.net) : meme chemin sur le CDN actuel.
    url = url.replace("://gog-cdn-lumen.secure2.footprint.net/", "://gog-cdn-fastly.gog.com/")
    return json.loads(zlib.decompress(_get(url).content))


def _manifest_url(manifest_id):
    return f"{META_CDN}{manifest_id[:2]}/{manifest_id[2:4]}/{manifest_id}"


def latest_build(info):
    """Derniere version Windows publique de 2e generation (branche principale), ou None.
    Lue dans le product.json de GOG Database, qui garde la liste des builds avec leur lien :
    l'API de GOG (content-system.gog.com/products/<id>/os/windows/builds) repond "429 Too Many Requests" des 2 requetes en
    parallele (mesure du 30/09/2026), le CDN des manifestes non."""
    builds = [b for b in info.get("builds") or []
              if b.get("os") == "windows" and b.get("generation") == 2 and b.get("public")
              and not b.get("branch") and b.get("link")]
    return max(builds, key=lambda b: b["date_published"]) if builds else None


def _file_entry(item):
    """(taille, md5) d'un DepotFile. Un seul morceau : md5 du morceau ; plusieurs : md5 du
    fichier ; petit fichier range dans un conteneur (sfcRef) : taille du conteneur."""
    chunks = item.get("chunks") or []
    if "sfcRef" in item:
        size = item["sfcRef"].get("size", 0)
    else:
        size = sum(c.get("size", 0) for c in chunks)
    md5 = item.get("md5") or (chunks[0].get("md5") if len(chunks) == 1 else None)
    if size == 0 and not md5:
        md5 = "d41d8cd98f00b204e9800998ecf8427e"  # fichier vide
    return size, md5


def _depot_languages(depot):
    """Langues d'un depot ramenees aux cles de LANGUAGES : GOG ecrit aussi bien "en-US" que
    "en", "fr-FR" que "fr" (mesure sur 88 jeux : 79 "en-US", 7 "en")."""
    result = set()
    for code in depot.get("languages", []):
        if code == "*":
            result.add("*")
            continue
        prefix = code.split("-")[0].lower()
        result.update(lang for lang in LANGUAGES if lang.split("-")[0] == prefix)
    return result


def game_files(product_id, build):
    """{langue: {chemin: (taille, md5)}} pour le jeu de base (depots des DLC ignores)."""
    meta = _meta(build["link"])
    files = {lang: {} for lang in LANGUAGES}
    # Langues vraiment proposees : citees par un depot du jeu. Un depot '*' seul ne suffit
    # pas (DOOM 64, anglais seulement, finissait dans le DAT francais avec 1 fichier commun).
    offered = {lang for d in meta.get("depots", []) if str(d.get("productId")) == str(product_id)
               for lang in _depot_languages(d) if lang in LANGUAGES}
    # Fichiers communs d'abord : un fichier de langue du meme chemin les remplace ensuite.
    depots = sorted(meta.get("depots", []), key=lambda d: "*" not in d.get("languages", []))
    for depot in depots:
        if str(depot.get("productId")) != str(product_id):
            continue
        langs = _depot_languages(depot)
        targets = [lang for lang in offered if "*" in langs or lang in langs]
        if not targets:
            continue
        manifest = _meta(_manifest_url(depot["manifest"]))
        for item in manifest["depot"].get("items", []):
            # "support" : redistribuables (DirectX, VC++) installes hors du dossier du jeu.
            if item.get("type") != "DepotFile" or "support" in (item.get("flags") or []):
                continue
            size, md5 = _file_entry(item)
            if not md5:
                continue
            path = item["path"].replace("\\", "/")
            for lang in targets:
                files[lang][path] = (size, md5)
    return meta.get("installDirectory"), files


def process(product_id):
    started = time.monotonic()
    try:
        info = _get(f"{GOGDB}/products/{product_id}/product.json").json()
        kind, title = info.get("type"), info.get("title")
        if kind != "game":
            return {"id": product_id, "skip": f"type {kind}"}
        build = latest_build(info)
        if build is None:
            return {"id": product_id, "title": title, "skip": "pas de build v2 Windows public"}
        install_dir, files = game_files(product_id, build)
        return {"id": product_id, "title": title, "dir": install_dir or title, "build": build.get("id"),
                "version": build.get("version"), "files": files,
                "seconds": round(time.monotonic() - started, 1)}
    except Exception as e:  # prototype : on note l'echec et on continue
        return {"id": product_id, "skip": f"erreur {type(e).__name__}: {e}"}


def write_dat(path, language_name, games, lang):
    today = date.today()
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n<datafile>\n\t<header>\n')
        f.write(f"\t\t<name>GOG - Windows ({language_name})</name>\n")
        f.write(f"\t\t<description>GOG - Windows ({language_name}) - installed games ({today:%Y-%m-%d})</description>\n")
        f.write(f"\t\t<version>{today:%Y%m%d}</version>\n\t\t<date>{today:%Y-%m-%d}</date>\n")
        f.write("\t\t<author>auto-datfile-generator (GOG Galaxy public manifests, catalog: gogdb.org)</author>\n")
        f.write("\t\t<url>https://github.com/goldorakiller/auto-datfile-generator</url>\n")
        f.write('\t\t<clrmamepro forcepacking="unzip"/>\n\t\t<romvault forcepacking="fileonly"/>\n\t</header>\n')
        for g in sorted(games, key=lambda g: g["dir"].lower()):
            entries = g["files"][lang]
            if not entries:
                continue
            f.write(f"\t<game name={quoteattr(g['dir'])}>\n")
            f.write(f"\t\t<description>{escape(g['title'] or g['dir'])} (GOG {g['id']}, build {g['version']})</description>\n")
            for p in sorted(entries, key=str.lower):
                size, md5 = entries[p]
                f.write(f"\t\t<rom name={quoteattr(p)} size=\"{size}\" md5=\"{md5}\"/>\n")
            f.write("\t</game>\n")
        f.write("</datafile>\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=20, help="nombre de produits tires au hasard (0 = tous)")
    parser.add_argument("--ids", default="", help="identifiants imposes, separes par des virgules")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", default="gog")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    ids = [int(i) for i in args.ids.split(",") if i.strip()]
    if args.sample:
        all_ids = _get(f"{GOGDB}/ids.json").json()
        random.Random(args.seed).shuffle(all_ids)
        ids += [i for i in all_ids if i not in ids][: args.sample]

    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(process, ids))
    games = [r for r in results if "files" in r]

    os.makedirs(args.out, exist_ok=True)
    stamp = date.today().strftime("%Y%m%d")
    for lang, name in LANGUAGES.items():
        path = os.path.join(args.out, f"GOG - Windows ({name}) ({stamp}).dat")
        write_dat(path, name, games, lang)
        print(f"{path} : {os.path.getsize(path):,} octets")

    for r in results:
        if "files" in r:
            print(f"  JEU  {r['id']} {r['title']!r} -> {r['dir']!r} build {r['version']} : "
                  f"en {len(r['files']['en-US'])} fichiers, fr {len(r['files']['fr-FR'])}, {r['seconds']} s")
        else:
            print(f"  --   {r['id']} {r.get('title') or ''} : {r['skip']}")
    total = sum(len(g["files"]["en-US"]) for g in games)
    print(f"{len(ids)} produits, {len(games)} jeux, {total} fichiers (en), "
          f"{_stats['requests']} requetes, {time.monotonic() - t0:.0f} s")


if __name__ == "__main__":
    main()
