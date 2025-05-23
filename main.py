# main.py – Volledig herschreven met verbeterde ondersteuning voor berijmde psalmen

import os
import re
import requests
import logging
from fastapi import FastAPI, APIRouter, HTTPException, Query
from bs4 import BeautifulSoup
from urllib.parse import quote
from functools import lru_cache

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("psalm_api")

app = FastAPI()
api_router = APIRouter(prefix="/api")

@lru_cache(maxsize=1024)
def cached_get(url: str) -> str:
    logger.debug(f"GET: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "nl-NL,nl;q=0.9,en-US;q=0.8"
    }
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code == 200:
        return r.text
    raise HTTPException(status_code=r.status_code, detail=f"Fout bij ophalen van {url}")

@lru_cache(maxsize=150)
def get_max_berijmd_vers(psalm: int) -> int:
    bronnen = [
        f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID=1",
        f"https://www.liturgie.nu/psalmen/{psalm}",
        f"https://www.online-bijbel.nl/psalm/{psalm}"
    ]
    max_verzen = []
    for url in bronnen:
        try:
            html = cached_get(url)
            soup = BeautifulSoup(html, "html.parser")
            tekst = soup.get_text(separator="\n")
            kandidaten = [int(s) for s in tekst.split() if s.isdigit() and 1 <= int(s) <= 30]
            hoogste = max(kandidaten) if kandidaten else 0
            max_verzen.append(hoogste)
        except Exception as e:
            logger.warning(f"Fout bij {url}: {e}")
    geldige = [v for v in max_verzen if v > 0]
    if not geldige:
        raise HTTPException(status_code=404, detail=f"Geen versinfo voor psalm {psalm}.")
    return max(set(geldige), key=geldige.count)

def validate_berijmd_vers(psalm: int, vers: int):
    max_vers = get_max_berijmd_vers(psalm)
    if vers < 1 or vers > max_vers:
        raise HTTPException(status_code=400, detail=f"Psalm {psalm} heeft slechts {max_vers} verzen.")

def extract_vers_psalmboek(psalm: int, vers: int) -> str:
    url = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID={vers}#psvs"
    html = cached_get(url)
    soup = BeautifulSoup(html, "html.parser")
    vers_div = soup.find("div", id="psvs")
    if vers_div:
        text = vers_div.get_text(separator="\n", strip=True)
        return text
    raise HTTPException(status_code=404, detail="Vers niet gevonden op psalmboek.nl")

def extract_vers_onlinebijbel(psalm: int, vers: int) -> str:
    url = f"https://www.online-bijbel.nl/psalm/{psalm}"
    html = cached_get(url)
    soup = BeautifulSoup(html, "html.parser")
    tekst = soup.get_text(separator="\n")
    regels = [r.strip() for r in tekst.split("\n") if r.strip()]
    if vers <= len(regels):
        return regels[vers - 1]
    raise HTTPException(status_code=404, detail="Vers niet gevonden in online-bijbel")

def fallback_vers(psalm: int, vers: int) -> str:
    bronnen = [extract_vers_psalmboek, extract_vers_onlinebijbel]
    resultaten = []
    for bron in bronnen:
        try:
            resultaten.append(bron(psalm, vers))
        except Exception:
            continue
    uniek = list(set(resultaten))
    if len(uniek) == 1:
        return uniek[0]
    raise HTTPException(status_code=502, detail="Geen consistente versresultaten beschikbaar.")

@api_router.get("/psalm")
def psalm_endpoint(
    psalm: int = Query(..., ge=1, le=150),
    vers: int = Query(..., ge=1),
    bron: str = Query("psalmboek", description="Bron: psalmboek of onlinebijbel")
):
    validate_berijmd_vers(psalm, vers)
    if bron == "psalmboek":
        try:
            tekst = extract_vers_psalmboek(psalm, vers)
        except Exception:
            tekst = fallback_vers(psalm, vers)
    elif bron == "onlinebijbel":
        tekst = extract_vers_onlinebijbel(psalm, vers)
    else:
        raise HTTPException(status_code=400, detail="Ongeldige bronoptie")
    return {"psalm": psalm, "vers": vers, "tekst": tekst}

@app.get("/")
def root():
    return {"status": "Psalm API actief"}

app.include_router(api_router)
