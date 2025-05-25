from fastapi import FastAPI, HTTPException
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
async def fetch_psalmboek(ps, vs):
    url = f"https://psalmboek.nl/psalm/{ps:03d}/vers/{vs:02d}?berijming=1773"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    stanza = soup.select_one("div.verse-text")
    return stanza.get_text(strip=True) if stanza else None

async def fetch_onlinebijbel(ps, vs):
    firstlines = {
        # voeg hier voor versnummer eerstelijnen in per psalm; of haal dynamisch op
        8: "Gelijk het gras is ons kortstondig leven",
        # …
    }
    firstline = firstlines.get(vs)
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

async def fetch_ro(ps, vs):
    url = f"https://content.reformatorischeomroep.nl/psalmen/berijming-1773/{ps}/{vs}.txt"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    return r.text.strip() if r.status_code == 200 else None

SCRAPE_SOURCES = [fetch_psalmboek, fetch_onlinebijbel, fetch_ro]

### ────────────────────────────────────
###  API-routes
### ────────────────────────────────────
@app.get(
    "/api/psalm",
    response_model=PsalmVers,
    responses={"404": {"model": Error}},
    operation_id="get_psalm_vers",
    summary="Haal één berijmd psalmvers (1773)"
)
async def get_psalm_vers(psalm: int, vers: int):
    # probeer alle bronnen
    for fn in SCRAPE_SOURCES:
        try:
            txt = await fn(psalm, vers)
            if txt:
                return PsalmVers(psalm=psalm, vers=vers, text=txt)
        except Exception:
            continue
    raise HTTPException(status_code=404, detail="Psalmvers niet gevonden in 1773-berijming")

@app.get(
    "/api/psalm/max",
    response_model=int,
    responses={"404": {"model": Error}},
    operation_id="get_psalm_max",
    summary="Geef maximaal versnummer in 1773-berijming"
)
async def get_psalm_max(psalm: int):
    # hard-coded of uit database; hier eenvoudig via Psalmboek.nl tellen
    # (in jouw implementatie kun je dynamisch scrapen of een map aanleggen)
    # Voorbeeld: Psalm 103 heeft 11 verzen
    max_vers = {
        103: 11,
        # … vul voor alle 150 psalmen aan …
    }.get(psalm)
    if max_vers:
        return max_vers
    raise HTTPException(status_code=404, detail="Psalm niet gevonden")
