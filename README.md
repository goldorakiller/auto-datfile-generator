# Auto DAT file generator (fork RetroBat)

![Daily Rebuild Status](https://github.com/goldorakiller/auto-datfile-generator/actions/workflows/daily-rebuild.yml/badge.svg)

Fork de [dantob/auto-datfile-generator](https://github.com/dantob/auto-datfile-generator),
étendu pour servir de source de données à [RBTools](https://github.com/goldorakiller/RBTools) :
agréger des DATs depuis de nombreux fournisseurs, publier chaque fichier
individuellement, et croiser le tout avec la liste officielle des systèmes
RetroBat pour produire un mapping "système -> DAT candidats".

Rebuild automatique une fois par 24h (`workflow_dispatch` disponible aussi).

## Sources mirrorées

Chaque source = un script Python indépendant, une étape de workflow, un
dossier de sortie. Une source qui échoue (panne réseau ponctuelle, etc.)
n'empêche pas les autres de tourner.

| Dossier | Source amont | Mécanisme |
|---|---|---|
| `no-intro/` | manifeste dantob (No-Intro) | XML, un fichier par jeu |
| `redump/` | manifeste dantob (Redump) | XML |
| `tosec/` | [tosecdev.org](https://www.tosecdev.org/downloads) — release courante | zip "Complete" scrappé (pas d'URL fixe), extrait par fichier |
| `whdload/` | Retroplay WHDLoad Packs (zips à la racine uniquement) | zip -> dat |
| `pleasuredome-mame/` | [Pleasuredome](https://pleasuredome.github.io/pleasuredome/mame/) — sets complets (pas les deltas "Update") | zip -> xml/dat |
| `pleasuredome-hbmame/` | idem, HBMAME | zip -> xml/dat |
| `pleasuredome-pinmame/` | idem, PinMAME | zip -> xml/dat |
| `visual-pinball/`, `future-pinball/` | Pleasuredome Pinball (deux dossiers séparés) | zip -> xml/dat |
| `fbneo/` | [libretro/FBNeo](https://github.com/libretro/FBNeo/tree/master/dats) | déjà un fichier par système |
| `libretro-database-dat/` | [libretro/libretro-database](https://github.com/libretro/libretro-database/tree/master/dat) | déjà un fichier par système (~48) |
| `libretro-database-metadat/{mame-split,mame,no-intro,redump,tosec}/` | [libretro/libretro-database](https://github.com/libretro/libretro-database/tree/master/metadat) | déjà un fichier par système |
| `Eggmansworld - Datfiles/` | [Eggmansworld/Datfiles](https://github.com/Eggmansworld/Datfiles/releases) — 19 collections, toutes les releases, dossier plat | zip `*_RomVault.zip` -> dat/xml |
| `clean-cpc-db/` | [clean-cpc-db/dat](https://github.com/clean-cpc-db/dat) | mirroir manuel (upstream non automatisé) |
| `fbneo-subsets/`, `mame-subsets/` | **fabriqués ici** par `arcade-subsets.py` à partir de `fbneo/` (Arcade only) et `pleasuredome-mame/` (ROMs non-merged) | un DAT par carte arcade (CAVE, CPS-1/2/3, Model 2/3, Hikaru, ZN, Gaelco PowerVR) et les consoles plug & play (TV Games, pilotes MAME `tvgames/`), filtré par l'attribut `sourcefile` de chaque jeu |
| `eggmansworld-subsets/` | **fabriqués ici** par `eggmansworld-subsets.py` à partir de `Eggmansworld - Datfiles/` | les jeux seuls d'une collection (ex. `Ares - LaserActive Discs` : les 47 disques `.mmi`, sans BIOS, émulateur, scans ni outils, `forcepacking="fileonly"`) |
| `teknoparrot-subsets/` | **fabriqués ici** par `teknoparrot-subsets.py` depuis la release de [Eggmansworld/TeknoParrot](https://github.com/Eggmansworld/TeknoParrot) (zip téléchargé, jamais commité : dat de ~620 Mo) | jeux d'une carte renommés d'après leur profil TeknoParrot comme l'exige RetroBat (ex. `TeknoParrot - Namco System 357-369` : 19 jeux, dossiers `<GameProfile>.game`), `forcepacking="fileonly"` |
| *(release uniquement)* `TeknoParrot-RetroBat.datz` | **fabriqué ici** par le même script : tous les autres jeux TeknoParrot, dossiers `<GameProfile>.teknoparrot` (un seul jeu par profil : le premier dans l'ordre d'Eggman, les doublons sont listés dans le journal) | dat gzip (~145 Mo, lu tel quel par ROMVault) trop gros pour git : publié uniquement comme pièce jointe de la release `Daily_Rebuild` |

**Fichiers volumineux exclus** : la limite git est de 100 Mo par fichier
versionné. Sont donc ignorés : la TeknoParrot Collection brute (617 Mo,
remplacée par les sous-ensembles ci-dessus), "Sega ALLS" d'Eggmansworld (421 Mo), "MAME 2015 XML.zip" de
libretro-database (166 Mo) — comportement attendu, pas un bug.

Différés (pas de mécanisme de distribution automatisable trouvé, ou
nécessitent une clé API personnelle) : GameTDB, World of Spectrum, Clean CPC
DB au-delà du mirroir manuel existant.

## `retrobat-systems.json`

Script `retrobat-systems.py`, dernière étape du workflow, tourne après toutes
les sources ci-dessus. Il télécharge la liste officielle des systèmes
RetroBat (`es_systems.cfg`), et pour chacun cherche des candidats dans
l'ensemble des sources mirrorées, par rapprochement de mots entiers (pas de
sous-chaîne — "mame" ne matche pas "hbmame").

Deux listes d'exclusion, faciles à étendre sans toucher à la logique de
matching :
- `EXCLUDED_KEYWORDS` : exclut un catalogue si son nom contient un mot donné
  (ex. "magazines").
- `EXCLUDED_SYSTEMS` : force zéro candidat pour un système RetroBat donné,
  même si le matching en trouverait (ex. "flash" — les correspondances
  lexicalement correctes trouvées ne sont pas les bonnes en pratique).

Format de sortie :

```json
[
  {
    "SystemCode": "3do",
    "FullName": "3DO",
    "Candidates": [
      { "Source": "No-Intro", "Name": "...", "Version": "...", "Url": "...", "File": "..." }
    ]
  }
]
```

Publié à chaque rebuild comme asset de la release `Daily_Rebuild`, et
consommé par RBTools pour proposer les DATs candidats par système.

## Workflow

`.github/workflows/daily-rebuild.yml` : `push` sur master, cron quotidien
(16h30 UTC), et déclenchement manuel. Un seul run à la fois
(`concurrency: daily-rebuild`) pour éviter que deux runs se percutent sur le
`git push` final. Chaque fichier DAT individuel est commité dans le repo (pas
seulement livré en zip de release) pour que chaque manifeste puisse pointer
dessus directement via `raw.githubusercontent.com`, sans que le client
(RBTools) ait besoin de télécharger un zip complet pour en extraire un seul
fichier.

## URLs (profils clrmamepro hérités du projet d'origine)

### No-Intro

`https://github.com/goldorakiller/auto-datfile-generator/releases/latest/download/no-intro.xml`

### No-Intro (parent-clone)

`https://github.com/goldorakiller/auto-datfile-generator/releases/latest/download/no-intro_parent-clone.xml`

### Redump

`https://github.com/goldorakiller/auto-datfile-generator/releases/latest/download/redump.xml`

### RetroBat systems mapping

`https://github.com/goldorakiller/auto-datfile-generator/releases/latest/download/retrobat-systems.json`

### TeknoParrot (RetroBat)

`https://github.com/goldorakiller/auto-datfile-generator/releases/download/Daily_Rebuild/TeknoParrot-RetroBat.datz`

Projet d'origine inspiré de [redump-xml-updater](https://github.com/bilakispa/redump-xml-updater)
