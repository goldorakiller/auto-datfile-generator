# Auto DAT file generator

![Daily Rebuild Status](https://github.com/dantob/auto-datfile-generator/actions/workflows/daily-rebuild.yml/badge.svg)

WWW profiles to use in clrmamepro for the standard No-Intro and Redump sets.
Refreshes once every 24h automatically.

## URLs

### No-Intro

`https://github.com/dantob/auto-datfile-generator/releases/latest/download/no-intro.xml`

### No-Intro (parent-clone)

`https://github.com/dantob/auto-datfile-generator/releases/latest/download/no-intro_parent-clone.xml`

### Redump

`https://github.com/dantob/auto-datfile-generator/releases/latest/download/redump.xml`

![clrmamepro screenshot](./img/clrmamepro.png)

Project inspired by [redump-xml-updater](https://github.com/bilakispa/redump-xml-updater)

## Header support

Some No-Intro dats require an extra XML file to detect headers.

![clrmamepro header warning screenshot](./img/headers.png)

Download the following zips, extract them and place the XML files in clrmamepro's `headers` folder:

- [Atari Jaguar](https://datomatic.no-intro.org/stuff/header_a7800.zip)
- [Atari Lynx](https://datomatic.no-intro.org/stuff/header_lynx.zip)
- [Nintendo FDS](https://datomatic.no-intro.org/stuff/header_fds.zip)
- [Nintendo NES](https://datomatic.no-intro.org/stuff/header_nes.zip)
