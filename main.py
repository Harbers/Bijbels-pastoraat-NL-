from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.responses import FileResponse
import httpx
from bs4 import BeautifulSoup

app = FastAPI()

class PsalmVers(BaseModel):
    psalm: int
    vers: int
    text: str
    bron: str

class Error(BaseModel):
    detail: str

# Scraper 1 – psalmboek.nl via zingen.php
async def fetch_psalmboek_zingen(ps: int, vs: int):
    url = f"https://psalmboek.nl/zingen.php?psalm={ps}&psvID={vs}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    content = soup.select_one("div.content") or soup
    p = content.find("p")
    return p.get_text(strip=True) if p else None, "psalmboek.nl/zingen.php"

# Scraper 2 – psalmboek.nl directe verslink
async def fetch_psalmboek_old(ps: int, vs: int):
    url = f"https://psalmboek.nl/psalm/{ps:03d}/vers/{vs:02d}?berijming=1773"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    stanza = soup.select_one("div.verse-text")
    return stanza.get_text(strip=True) if stanza else None, "psalmboek.nl/psalm"

# Scraper 3 – fallback: reformatorischeomroep.nl
async def fetch_reformatorischeomroep(ps: int, vs: int):
    url = f"https://content.reformatorischeomroep.nl/psalmen/berijming-1773/{ps}/{vs}.txt"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    return r.text.strip() if r.status_code == 200 else None, "reformatorischeomroep.nl"

# Prioriteit: zingenscraper, dan oud, dan RO
SCRAPERS = [
    fetch_psalmboek_zingen,
    fetch_psalmboek_old,
    fetch_reformatorischeomroep
]

@app.get("/api/debug/vers", response_model=PsalmVers, responses={404: {"model": Error}})
async def get_berijmd_psalmvers(psalm: int, vers: int):
    for scraper in SCRAPERS:
        try:
            result = await scraper(psalm, vers)
            if result and result[0]:
                return PsalmVers(psalm=psalm, vers=vers, text=result[0], bron=result[1])
        except Exception:
            continue
    raise HTTPException(status_code=404, detail=f"Psalm {psalm}:{vers} niet gevonden in de 1773-berijming")

@app.get("/api/psalm/max", response_model=int, responses={404: {"model": Error}})
async def get_psalm_max(psalm: int):
    url = f"https://psalmboek.nl/zingen.php?psalm={ps}&psvID=8"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        r = await client.get(url)
    if r.status_code != 200:
        raise HTTPException(status_code=404, detail="Psalm niet gevonden")
    soup = BeautifulSoup(r.text, "html.parser")
    opts = soup.select("select[name=vers] option")
    waarden = [o.get("value") for o in opts if o.get("value", "").isdigit()]
    if not waarden:
        raise HTTPException(status_code=404, detail="Geen verzen gevonden")
    return max(int(v) for v in waarden)

@app.get("/openapi.yaml", include_in_schema=False)
async def openapi_spec():
    return FileResponse("openapi.yaml", media_type="application/yaml")
