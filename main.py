# main.py – Volledig herschreven met verbeterde scraping en versvalidatie

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
    """
    Bepaal het aantal verzen in de berijmde versie van een psalm op basis van scraping van psalmboek.nl
    """
    url = f"https://psalmboek.nl/zingen.php?psalm={psalm}"
    html = cached_get(url)
    soup = BeautifulSoup(html, "html.parser")

    # Zoek naar versnummers links van de tekst (nummerlijst)
    vers_knoppen = soup.select(".inhoud-verslijst a") or soup.select(".versen a")
    vers_nummers = set()

    for knop in vers_knoppen:
        try:
            nummer = int(knop.text.strip())
            vers_nummers.add(nummer)
        except ValueError:
            continue

    if not vers_nummers:
        # Fallback: tel kopregels zoals "Psalm 103 vers 1"
        teksten = soup.get_text("\n").split("\n")
        for regel in teksten:
            if f"Psalm {psalm} vers " in regel:
                try:
                    v = int(regel.strip().split("vers")[-1].strip())
                    vers_nummers.add(v)
                except:
                    continue

    if not vers_nummers:
        raise HTTPException(status_code=404, detail=f"Geen versnummers gevonden voor Psalm {psalm}.")

    hoogste = max(vers_nummers)
    logger.debug(f"Psalm {psalm} heeft {hoogste} verzen volgens scraping.")
    return hoogste

def validate_berijmd_vers(psalm: int, vers: int):
    max_vers = get_max_berijmd_vers(psalm)
    if vers < 1 or vers > max_vers:
        raise HTTPException(
            status_code=400,
            detail=f"Er is geprobeerd om Psalm {psalm}:{vers} (berijmd, 1773) op te halen, maar dit vers blijkt niet te bestaan. Het hoogste beschikbare versnummer voor Psalm {psalm} is {max_vers}."
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

def fallback_vers(psalm: int, vers: int) -> str:
    bronnen = [extract_vers_psalmboek, extract_vers_onlinebijbel]
    resultaten = []
    for f in bronnen:
        try:
            tekst = f(psalm, vers)
            if tekst:
                resultaten.append(tekst.strip())
        except:
            continue
    uniek = list(set(resultaten))
    if len(uniek) == 1:
        return uniek[0]
    elif len(uniek) > 1:
        return "\n\n".join(uniek)
    raise HTTPException(status_code=502, detail="Geen betrouwbare fallbacktekst beschikbaar")

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
        except:
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
