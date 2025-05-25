from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup

app = FastAPI()

class PsalmVers(BaseModel):
    psalm: int
    vers: int
    text: str

class Error(BaseModel):
    detail: str

async def fetch_psalmboek(ps: int, vs: int) -> str | None:
    """
    Haalt de tekst uit psalmboek.nl (div.verse-text).
    """
    url = f"https://psalmboek.nl/psalm/{ps:03d}/vers/{vs:02d}?berijming=1773"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    node = soup.select_one("div.verse-text")
    return node.get_text(" ", strip=True) if node else None

async def fetch_onlinebijbel(ps: int, vs: int) -> str | None:
    """
    Fallback scraper op basis van Online-Bijbel.nl.
    (Voor sommige eerste regels; breid zelf uit.)
    """
    firstlines = {
        8: "Gelijk het gras is ons kortstondig leven",
        # voeg hier meer verse → eerste regel mappings toe
    }
    first = firstlines.get(vs)
    if not first:
        return None
    url = f"https://www.online-bijbel.nl/psalmen-1773/{ps}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200 or first not in r.text:
        return None
    start = r.text.find(first)
    end = r.text.find("<br/>", start)
    snippet = r.text[start:end]
    return BeautifulSoup(snippet, "html.parser").get_text(" ", strip=True)

async def fetch_ro(ps: int, vs: int) -> str | None:
    """
    Tekst via Reformatorische Omroep (plain-text endpoint).
    """
    url = f"https://content.reformatorischeomroep.nl/psalmen/berijming-1773/{ps}/{vs}.txt"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    return r.text.strip() if r.status_code == 200 else None

SCRAPE_SOURCES = [
    fetch_psalmboek,
    fetch_onlinebijbel,
    fetch_ro,
]

@app.get(
    "/api/psalm",
    response_model=PsalmVers,
    responses={"404": {"model": Error}},
    operation_id="get_psalm_vers",
    summary="Haal één berijmd psalmvers (1773)"
)
async def get_psalm_vers(psalm: int, vers: int):
    """
    Probeert in volgorde alle scrapers totdat één tekst oplevert.
    """
    for scraper in SCRAPE_SOURCES:
        try:
            txt = await scraper(psalm, vers)
            if txt:
                return PsalmVers(psalm=psalm, vers=vers, text=txt)
        except Exception:
            continue
    raise HTTPException(
        status_code=404,
        detail="Psalmvers niet gevonden in 1773-berijming"
    )

@app.get(
    "/api/psalm/max",
    response_model=int,
    responses={"404": {"model": Error}},
    operation_id="get_psalm_max",
    summary="Geef maximaal versnummer in 1773-berijming"
)
async def get_psalm_max(psalm: int):
    """
    Dynamisch het aantal verzen tellen door de optie-lijst op psalmboek.nl uit te lezen.
    """
    url = f"https://psalmboek.nl/psalm/{psalm:03d}?berijming=1773"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        raise HTTPException(status_code=404, detail="Psalm niet gevonden")
    soup = BeautifulSoup(r.text, "html.parser")
    select = soup.find("select", id="select-vers")
    if not select:
        raise HTTPException(status_code=404, detail="Psalm niet gevonden")
    options = select.find_all("option")
    if not options:
        raise HTTPException(status_code=404, detail="Geen verzen gevonden")
    max_vers = int(options[-1]["value"])
    return max_vers
