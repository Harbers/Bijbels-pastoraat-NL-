from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup

app = FastAPI(
    title="Bijbelse Psalmen API",
    version="1.0",
    openapi_url="/openapi.yaml",
    docs_url="/docs"
)

# Serveer de plugin-manifest en statische bestanden uit .well-known/
app.mount(
    "/.well-known",
    StaticFiles(directory=".well-known", html=False),
    name="well-known"
)

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
    container = soup.select_one("div.content") or soup
    paragraphs = container.find_all("p")
    if not paragraphs:
        return None
    # behoud originele regelbreaks en spaties
    text = "\n".join(p.get_text(strip=False) for p in paragraphs)
    return text, "psalmboek.nl/zingen.php"

# Scraper 2 – psalmboek.nl directe verslink
async def fetch_psalmboek_old(ps: int, vs: int):
    url = f"https://psalmboek.nl/psalm/{ps:03d}/vers/{vs:02d}?berijming=1773"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    stanza = soup.select_one("div.verse-text")
    if not stanza:
        return None
    # gebruik newline-separator, geen strip
    text = stanza.get_text(separator="\n", strip=False)
    return text, "psalmboek.nl/psalm"

# Scraper 3 – reformatorischeomroep.nl
async def fetch_reformatorischeomroep(ps: int, vs: int):
    url = f"https://content.reformatorischeomroep.nl/psalmen/berijming-1773/{ps}/{vs}.txt"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    text = r.text  # plain text al met juiste breaks
    return text, "reformatorischeomroep.nl"

SCRAPERS = [
    fetch_psalmboek_zingen,
    fetch_psalmboek_old,
    fetch_reformatorischeomroep
]

@app.get(
    "/api/debug/vers",
    response_model=PsalmVers,
    responses={404: {"model": Error}}
)
async def get_berijmd_psalmvers(
    psalm: int = Query(..., ge=1, le=150),
    vers:  int = Query(..., ge=1)
):
    for scraper in SCRAPERS:
        try:
            result = await scraper(psalm, vers)
            if result:
                text, bron = result
                return PsalmVers(psalm=psalm, vers=vers, text=text, bron=bron)
        except Exception:
            continue
    raise HTTPException(
        status_code=404,
        detail=f"Psalm {psalm}:{vers} niet gevonden in de 1773-berijming"
    )

@app.get(
    "/api/psalm/max",
    response_model=int,
    responses={404: {"model": Error}}
)
async def get_psalm_max(
    psalm: int = Query(..., ge=1, le=150)
):
    url = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID=8"
    async with httpx.AsyncClient(timeout=10) as client:
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
