import os
import shutil
from contextlib import contextmanager


@contextmanager
def replace_directory(path):
    """Prepare un dossier temporaire, le fournit au bloc appelant, puis ne
    l'echange avec `path` qu'une fois le bloc termine SANS exception.

    But : un mirror doit toujours refleter l'etat actuel de la source (pas
    d'anciennes versions qui trainent a cote des nouvelles), mais une panne
    reseau transitoire pendant le telechargement ne doit jamais effacer un
    mirror qui marchait la veille. Vider `path` avant de re-fetcher faisait
    exactement ca (constate en reel sur whdload.py : une panne DNS
    transitoire sur ftp2.grandis.nu a fait disparaitre tout le dossier
    whdload/ du repo, alors qu'avant ce changement une panne transitoire ne
    faisait juste rien).
    """
    tmp_path = f"{path}.tmp"
    shutil.rmtree(tmp_path, ignore_errors=True)
    os.makedirs(tmp_path, exist_ok=True)
    try:
        yield tmp_path
    except BaseException:
        shutil.rmtree(tmp_path, ignore_errors=True)
        raise
    else:
        shutil.rmtree(path, ignore_errors=True)
        os.replace(tmp_path, path)
