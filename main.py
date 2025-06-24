from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup

app = FastAPI(
    title="Bijbelse Psalmen API",
    version="1.0"
)

class PsalmVers(BaseModel):
    psalm: int
    vers: int
    text: str
    bron: str

class Error(BaseModel):
    detail: str

# Endpoint om ai-plugin.json te serveren
@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
async def serve_ai_plugin():
    return FileResponse("ai-plugin.json", media_type="application/json")

# Endpoint om openapi.yaml te serveren
@app.get("/openapi.yaml", include_in_schema=False)
async def serve_openapi():
    return FileResponse("openapi.yaml", media_type="text/yaml")

# Scrapers
async def fetch_from_zingen(ps: int, vs: int):
    url = f"https://psalmboek.nl/zingen.php?psalm={ps}&psvID={vs}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    p = soup.select_one("div.content p") or soup.find("p")
    if not p:
        return None
    return p.get_text(separator="\n", strip=True), "psalmboek.nl/zingen.php"

async def fetch_from_old(ps: int, vs: int):
    url = f"https://psalmboek.nl/psalm/{ps:03d}/vers/{vs:02d}?berijming=1773"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    stanza = soup.select_one("div.verse-text")
    if not stanza:
        return None
    return stanza.get_text(separator="\n", strip=True), url

async def fetch_from_refo(ps: int, vs: int):
    url = f"https://content.reformatorischeomroep.nl/psalmen/berijming-1773/{ps}/{vs}.txt"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    text = r.text.strip()
    return (text, url) if text else None

SCRAPERS = [fetch_from_zingen, fetch_from_old, fetch_from_refo]

@app.get("/api/psalm", response_model=PsalmVers, responses={404: {"model": Error}})
async def get_psalm_vers(
    psalm: int = Query(..., ge=1, le=150),
    vers: int = Query(..., ge=1)
):
    for scraper in SCRAPERS:
        result = await scraper(psalm, vers)
        if result:
            text, bron = result
            return PsalmVers(psalm=psalm, vers=vers, text=text, bron=bron)
    raise HTTPException(status_code=404, detail=f"Vers {vers} van Psalm {psalm} kon niet worden opgehaald.")

@app.get("/api/psalm/max", response_model=int, responses={404: {"model": Error}})
async def get_psalm_max(psalm: int = Query(..., ge=1, le=150)):
    url = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID=0"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        raise HTTPException(status_code=404, detail=f"Psalm {psalm} niet gevonden.")
    soup = BeautifulSoup(r.text, "html.parser")
    opts = soup.select("select[name=psvID] option")
    waarden = [o["value"] for o in opts if o.get("value", "").isdigit()]
    if not waarden:
        raise HTTPException(status_code=404, detail=f"Geen verzen gevonden voor Psalm {psalm}.")
    return max(int(v) for v in waarden)
