from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup

app = FastAPI(
    title="Bijbelse Psalmen Scraper API",
    version="1.0"
)

# 1) serve alles uit .well-known (plugin-manifest, logo, etc.)
app.mount("/.well-known", StaticFiles(directory=".well-known"), name="well-known")

class PsalmVers(BaseModel):
    psalm: int
    vers: int
    text: str

class Error(BaseModel):
    detail: str

async def fetch_psalmboek(ps: int, vs: int) -> str | None:
    url = f"https://psalmboek.nl/psalm/{ps:03d}/vers/{vs:02d}?berijming=1773"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
    if resp.status_code != 200:
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    node = soup.select_one("div.verse-text")
    return node.get_text(strip=True) if node else None

async def fetch_onlinebijbel(ps: int, vs: int) -> str | None:
    url = f"https://www.online-bijbel.nl/psalmen-1773/{ps}"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
    if resp.status_code != 200:
        return None
    marker = f"{vs}. "
    idx = resp.text.find(marker)
    if idx < 0:
        return None
    start = idx + len(marker)
    end = resp.text.find("<br/>", start)
    snippet = resp.text[start:end]
    return BeautifulSoup(snippet, "html.parser").get_text(strip=True)

async def fetch_ro(ps: int, vs: int) -> str | None:
    url = f"https://content.reformatorischeomroep.nl/psalmen/berijming-1773/{ps}/{vs}.txt"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
    return resp.text.strip() if resp.status_code == 200 else None

SCRAPE_SOURCES = [fetch_psalmboek, fetch_onlinebijbel, fetch_ro]

async def get_max_vers(ps: int) -> int:
    url = f"https://psalmboek.nl/psalm/{ps:03d}?berijming=1773"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
    if resp.status_code != 200:
        raise HTTPException(status_code=404, detail=f"Psalm {ps} niet gevonden")
    soup = BeautifulSoup(resp.text, "html.parser")
    verses = soup.select("div.verse-text")
    if not verses:
        raise HTTPException(status_code=404, detail=f"Psalm {ps} bevat geen verzen")
    return len(verses)

@app.get(
    "/api/psalm/max",
    response_model=int,
    responses={404: {"model": Error}},
    summary="Geef maximaal versnummer in 1773-berijming"
)
async def api_get_psalm_max(
    psalm: int = Query(..., ge=1, le=150)
):
    return await get_max_vers(psalm)

@app.get(
    "/api/psalm",
    response_model=PsalmVers,
    responses={400: {"model": Error}, 404: {"model": Error}},
    summary="Haal één berijmd psalmvers (1773)"
)
async def api_get_psalm_vers(
    psalm: int = Query(..., ge=1, le=150),
    vers:  int = Query(..., ge=1)
):
    max_vers = await get_max_vers(psalm)
    if vers > max_vers:
        raise HTTPException(
            status_code=400,
            detail=f"Psalm {psalm} heeft maximaal {max_vers} verzen, gevraagd {vers}."
        )
    for src in SCRAPE_SOURCES:
        try:
            txt = await src(psalm, vers)
            if txt:
                return PsalmVers(psalm=psalm, vers=vers, text=txt)
        except Exception:
            continue
    raise HTTPException(status_code=404, detail="Psalmvers niet gevonden in 1773-berijming")
