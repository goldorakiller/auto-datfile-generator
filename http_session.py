import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def retrying_session():
    """Session requests qui retente une requete GET en cas de coupure reseau,
    de delai depasse ou d'erreur serveur/limite de debit (429, 5xx).

    But : les runners GitHub Actions voient des pannes transitoires que l'on
    ne voit pas depuis un poste (constate en reel sept. 2026 : whdload.py en
    echec 8 runs sur 15 alors que le meme script passe en local). 4 nouvelles
    tentatives, apres 0, 10, 20 puis 40 s (backoff_factor=5, mesure : ~80 s
    avant d'abandonner) : une coupure de moins d'une minute ne fait plus
    echouer toute la source."""
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def github_api_headers():
    """En-tetes pour api.github.com : avec le jeton du workflow (GITHUB_TOKEN)
    s'il est present, la limite passe de 60 requetes/heure par adresse IP
    (partagee entre tous les jobs d'un meme runner) a celle du depot. En local
    sans jeton, rien ne change."""
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers
