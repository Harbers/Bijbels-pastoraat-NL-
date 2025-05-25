# main.py

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup

app = FastAPI()

### ────────────────────────────────────
###  Datamodellen
### ────────────────────────────────────
class PsalmVers(BaseModel):
    psalm: int
    vers: int
    text: str

class Error(BaseModel):
    detail: str

### ────────────────────────────────────
###  Scraping-helpers
### ────────────────────────────────────
async def fetch_psalmboek(ps: int, vs: int) -> str | None:
    """
    Bron 1 – psalmboek.nl
    URL-patroon: https://psalmboek.nl/psalm/{ps:03d}/vers/{vs:02d}?berijming=1773
    """
    url = f"https://psalmboek.nl/psalm/{ps:03d}/vers/{vs:02d}?berijming=1773"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
    if resp.status_code != 200:
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    stanza = soup.select_one("div.verse-text")
    return stanza.get_text(strip=True) if stanza else None

async def fetch_onlinebijbel(ps: int, vs: int) -> str | None:
    """
    Bron 2 – online-bijbel.org
    De site groepeert coupletten anders; daarom zoeken we op de eerste regel.
    """
    # Pas deze firstlines-dict aan per vers, of bouw een generieke parser
    firstline_map = {
        8: "Gelijk het gras is ons kortstondig leven"
    }
    firstline = firstline_map.get(vs)
    if not firstline:
        return None

    url = f"https://www.online-bijbel.nl/psalmen-1773/{ps}"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
    if resp.status_code != 200:
        return None

    html = resp.text
    idx = html.find(firstline)
    if idx == -1:
        return None

    # eenvoudige extractie tot de volgende <br/>
    end = html.find("<br", idx)
    snippet = html[idx:end]
    return BeautifulSoup(snippet, "html.parser").get_text(strip=True)

async def fetch_ro(ps: int, vs: int) -> str | None:
    """
    Bron 3 – Reformatorische Omroep (plain-text index)
    """
    url = f"https://content.reformatorischeomroep.nl/psalmen/berijming-1773/{ps}/{vs}.txt"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
    if resp.status_code != 200:
        return None
    return resp.text.strip()

SCRAPE_SOURCES = [
    fetch_psalmboek,
    fetch_onlinebijbel,
    fetch_ro,
]

### ────────────────────────────────────
###  API-route
### ────────────────────────────────────
@app.get(
    "/api/debug/vers",
    response_model=PsalmVers,
    responses={404: {"model": Error}},
)
async def get_berijmd_psalmvers(
    psalm: int = Query(..., ge=1, le=150, description="Psalmnummer (1–150)"),
    vers:  int = Query(..., ge=1,       description="Versnummer (≥ 1)")
):
    """
    Zoekt het gevraagde vers achtereenvolgens in drie openbare bronnen.
    Wordt nergens een resultaat gevonden → 404.
    """
    for fetch_fn in SCRAPE_SOURCES:
        try:
            text = await fetch_fn(psalm, vers)
        except Exception:
            # bron onbereikbaar of parserfout? probeer volgende
            continue

        if text:
            return PsalmVers(psalm=psalm, vers=vers, text=text)

    # geen bron gaf resultaat
    raise HTTPException(
        status_code=404,
        detail="Psalmvers niet gevonden in 1773-berijming"
    )
