import json
import os

from dat_catalog import build_catalog_index, load_all_catalogs

OUTPUT_FILE = "retrobat-systems.json"

# Rafraichissement PUR : ce script ne construit plus retrobat-systems.json
# depuis zero (voir historique : le rapprochement automatique par nom est
# fragile — un renommage upstream, un mot trop generique, une regex trop
# stricte peuvent casser un systeme entier du jour au lendemain sans que
# personne n'ait rien change). Desormais retrobat-systems.json est un
# fichier CURATE a la main (quels candidats appartiennent a quel systeme,
# decide par Cedric) ; ce script se contente de retrouver, pour chaque
# candidat deja present, l'entree fraiche correspondante dans les
# catalogues qui viennent d'etre mirrores, et de rafraichir Version/Url/
# File si ca a change. Rien n'est jamais ajoute ni retire automatiquement.
#
# Le rapprochement automatique par nom existe toujours, mais dans un outil
# separe (retrobat-systems-discover.py), lance a la demande — il propose
# des candidats a ajouter, ne modifie jamais ce fichier lui-meme.


def refresh():
    if not os.path.exists(OUTPUT_FILE):
        raise RuntimeError(
            f"{OUTPUT_FILE} introuvable : ce script rafraichit seulement "
            "les candidats deja presents, il ne (re)construit plus le "
            "fichier depuis zero. Voir retrobat-systems-discover.py pour "
            "proposer un premier jet de candidats a fusionner a la main."
        )

    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        results = json.load(f)

    print("Loading catalogs ...")
    catalogs = load_all_catalogs()
    index = build_catalog_index(catalogs)

    refreshed = 0
    stale = 0
    for system in results:
        for candidate in system.get("Candidates", []):
            fresh = index.get(candidate.get("Source"), {}).get(candidate.get("Name"))
            if fresh is None:
                stale += 1
                print(
                    f"  INTROUVABLE (garde la derniere version connue) : "
                    f"{system['SystemCode']} / {candidate['Source']} / {candidate['Name']}"
                )
                continue

            if (candidate.get("Version") != fresh["version"]
                    or candidate.get("Url") != fresh["url"]
                    or candidate.get("File") != fresh["file"]):
                candidate["Version"] = fresh["version"]
                candidate["Url"] = fresh["url"]
                candidate["File"] = fresh["file"]
                refreshed += 1

    print(f"\n{refreshed} candidat(s) mis a jour, {stale} introuvable(s) dans les sources actuelles (conserves tels quels)")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUTPUT_FILE}")


try:
    refresh()
except KeyboardInterrupt:
    pass
