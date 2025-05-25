from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.responses import FileResponse
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
async def fetch_psalmboek_zingen(ps: int, vs: int):
    url = f"https://psalmboek.nl/zingen.php?psalm={ps}&psvID={vs}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    container = soup.select_one("div.content") or soup
    p = container.find("p")
    return p.get_text(strip=True) if p else None

async def fetch_psalmboek_old(ps: int, vs: int):
    url = f"https://psalmboek.nl/psalm/{ps:03d}/vers/{vs:02d}?berijming=1773"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    stanza = soup.select_one("div.verse-text")
    return stanza.get_text(strip=True) if stanza else None

async def fetch_onlinebijbel(ps: int, vs: int):
    firstline_map = {
        8: "Gelijk het gras is ons kortstondig leven",
    }
    firstline = firstline_map.get(vs)
    if not firstline:
        return None
    url = f"https://www.online-bijbel.nl/psalmen-1773/{ps}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200 or firstline not in r.text:
        return None
    start = r.text.find(firstline)
    end = r.text.find("<br/>", start)
    return BeautifulSoup(r.text[start:end], "html.parser").get_text(strip=True)

async def fetch_reformatorischeomroep(ps: int, vs: int):
    url = f"https://content.reformatorischeomroep.nl/psalmen/berijming-1773/{ps}/{vs}.txt"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    return r.text.strip() if r.status_code == 200 else None

SCRAPE_SOURCES = [
    fetch_psalmboek_zingen,
    fetch_psalmboek_old,
    fetch_onlinebijbel,
    fetch_reformatorischeomroep,
]

### ────────────────────────────────────
###  API-routes
### ────────────────────────────────────
@app.get(
    "/api/debug/vers",
    response_model=PsalmVers,
    responses={404: {"model": Error}},
)
async def get_berijmd_psalmvers(psalm: int, vers: int):
    for scraper in SCRAPE_SOURCES:
        try:
            if (tekst := await scraper(psalm, vers)):
                return PsalmVers(psalm=psalm, vers=vers, text=tekst)
        except Exception:
            continue
    raise HTTPException(
        status_code=404,
        detail=f"Psalm {psalm}:{vers} niet gevonden in de 1773-berijming"
    )

@app.get("/openapi.yaml", include_in_schema=False)
async def openapi_spec():
    return FileResponse("openapi.yaml", media_type="application/yaml")
