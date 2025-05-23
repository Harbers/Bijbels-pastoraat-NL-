import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, APIRouter, HTTPException, Query
from functools import lru_cache
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("psalm_api")

app = FastAPI()
api_router = APIRouter(prefix="/api")

@lru_cache(maxsize=1024)
def cached_get(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "nl-NL,nl;q=0.9"
    }
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code == 200:
        return response.text
    raise HTTPException(status_code=response.status_code, detail=f"Fout bij ophalen van URL: {url}")

@lru_cache(maxsize=150)
def get_max_berijmd_vers(psalm: int) -> int:
    url = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID=1#psvs"
    html = cached_get(url)
    soup = BeautifulSoup(html, "html.parser")

    links = soup.select('a.psletter[href^="?psID="]')
    vers_nummers = set()

    for link in links:
        href = link.get("href", "")
        if "#psvs" in href and "?psID=" in href:
            try:
                nummer = int(href.split("?psID=")[1].split("#")[0])
                vers_nummers.add(nummer)
            except ValueError:
                continue

    if not vers_nummers:
        raise HTTPException(status_code=404, detail=f"Geen versnummers gevonden voor Psalm {psalm}.")

    hoogste = max(vers_nummers)
    logger.debug(f"Psalm {psalm} heeft {hoogste} verzen volgens links met ?psID=")
    return hoogste

def validate_berijmd_vers(psalm: int, vers: int):
    max_vers = get_max_berijmd_vers(psalm)
    if vers < 1 or vers > max_vers:
        raise HTTPException(
            status_code=400,
            detail=f"Psalm {psalm}:{vers} bestaat niet in de berijmde versie. Hoogste vers is {max_vers}."
        )

def extract_vers_psalmboek(psalm: int, vers: int) -> str:
    url = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID={vers}#psvs"
    html = cached_get(url)
    soup = BeautifulSoup(html, "html.parser")
    tekstblok = soup.find("div", id="psvs")
    if tekstblok:
        return tekstblok.get_text("\n", strip=True)
    raise HTTPException(status_code=404, detail="Vers niet gevonden bij psalmboek.nl")

def extract_vers_onlinebijbel(psalm: int, vers: int) -> str:
    url = f"https://www.online-bijbel.nl/psalm/{psalm}"
    html = cached_get(url)
    soup = BeautifulSoup(html, "html.parser")
    regels = [r.strip() for r in soup.get_text("\n").split("\n") if r.strip()]
    if vers <= len(regels):
        return regels[vers - 1]
    raise HTTPException(status_code=404, detail="Vers niet gevonden bij online-bijbel.nl")

@api_router.get("/psalm")
def psalm_endpoint(
    psalm: int = Query(..., ge=1, le=150),
    vers: int = Query(..., ge=1),
    bron: str = Query("psalmboek", description="Bron: psalmboek of onlinebijbel")
):
    validate_berijmd_vers(psalm, vers)

    if bron == "psalmboek":
        tekst = extract_vers_psalmboek(psalm, vers)
    elif bron == "onlinebijbel":
        tekst = extract_vers_onlinebijbel(psalm, vers)
    else:
        raise HTTPException(status_code=400, detail="Ongeldige bronoptie")

    return {"psalm": psalm, "vers": vers, "tekst": tekst}

@api_router.get("/psalm/max")
def psalm_max_endpoint(psalm: int = Query(..., ge=1, le=150)):
    max_vers = get_max_berijmd_vers(psalm)
    return {"psalm": psalm, "max_vers": max_vers}

@app.get("/debug/html")
def debug_html(psalm: int):
    html = cached_get(f"https://psalmboek.nl/zingen.php?psalm={psalm}")
    return {"html": html[:5000]}

@app.get("/")
def root():
    return {"status": "Psalm API actief"}

app.include_router(api_router)
