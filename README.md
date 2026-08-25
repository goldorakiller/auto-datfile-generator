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

**Fichiers volumineux exclus** : la limite git est de 100 Mo par fichier
versionné. Sont donc ignorés : TeknoParrot Collection (617 Mo, source entière
laissée de côté), "Sega ALLS" d'Eggmansworld (421 Mo), "MAME 2015 XML.zip" de
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

![clrmamepro screenshot](./img/clrmamepro.png)

Projet d'origine inspiré de [redump-xml-updater](https://github.com/bilakispa/redump-xml-updater)

## Header support

Certains DATs No-Intro nécessitent un fichier XML supplémentaire pour
détecter les headers.

![clrmamepro header warning screenshot](./img/headers.png)

Télécharger les zips suivants, les extraire et placer les XML dans le dossier
`headers` de clrmamepro :

- [Atari Jaguar](https://datomatic.no-intro.org/stuff/header_a7800.zip)
- [Atari Lynx](https://datomatic.no-intro.org/stuff/header_lynx.zip)
- [Nintendo FDS](https://datomatic.no-intro.org/stuff/header_fds.zip)
- [Nintendo NES](https://datomatic.no-intro.org/stuff/header_nes.zip)
