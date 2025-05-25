from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup

app = FastAPI()

# exposeer .well-known voor plugin manifest & spec
app.mount(
    "/.well-known",
    StaticFiles(directory=".well-known", html=False),
    name="well-known"
)

class PsalmVers(BaseModel):
    psalm: int
    vers: int
    text: str

class Error(BaseModel):
    detail: str

async def fetch_psalmboek(ps, vs):
    url = f"https://psalmboek.nl/psalm/{ps:03d}/vers/{vs:02d}?berijming=1773"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    node = soup.select_one("div.verse-text")
    return node.get_text(strip=True) if node else None

async def fetch_onlinebijbel(ps, vs):
    # eerste regel-mapping uitbreiden waar nodig
    firstlines = {
        8: "Gelijk het gras is ons kortstondig leven"
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
    return BeautifulSoup(r.text[start:end], "html.parser").get_text(strip=True)

async def fetch_ro(ps, vs):
    url = f"https://content.reformatorischeomroep.nl/psalmen/berijming-1773/{ps}/{vs}.txt"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    return r.text.strip() if r.status_code == 200 else None

SCRAPE_SOURCES = [fetch_psalmboek, fetch_onlinebijbel, fetch_ro]

@app.get(
    "/api/psalm",
    response_model=PsalmVers,
    responses={"404": {"model": Error}},
    operation_id="get_psalm_vers",
    summary="Haal één berijmd psalmvers (1773)"
)
async def get_psalm_vers(psalm: int, vers: int):
    for fn in SCRAPE_SOURCES:
        try:
            txt = await fn(psalm, vers)
            if txt:
                return PsalmVers(psalm=psalm, vers=vers, text=txt)
        except:
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
    max_vers = {103: 11, 42: 5, 89: 1, 32: 2}  # breid aan waar nodig
    mv = max_vers.get(psalm)
    if mv is not None:
        return mv
    raise HTTPException(status_code=404, detail="Psalm niet gevonden")
