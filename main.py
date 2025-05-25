# main.py

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup

app = FastAPI(
    title="Bijbelse Psalmen API",
    version="1.0",
    openapi_url=None,     # serve the spec manually
    docs_url="/docs"
)

# 1) Serve plugin manifest & icons from .well-known/
app.mount(
    "/.well-known",
    StaticFiles(directory=".well-known", html=False),
    name="well-known"
)

# 2) Serve own OpenAPI spec
@app.get("/openapi.yaml", include_in_schema=False)
async def openapi_spec():
    return FileResponse("openapi.yaml", media_type="application/x-yaml")


### ────────────────────────────────────
### Data models
### ────────────────────────────────────
class PsalmVers(BaseModel):
    psalm: int
    vers: int
    text: str
    bron: str

class Error(BaseModel):
    detail: str


### ────────────────────────────────────
### Helpers
### ────────────────────────────────────
async def fetch_max(ps: int) -> int | None:
    """Fetch max vers via psalmboek.nl/zingen.php?psvID=8"""
    url = f"https://psalmboek.nl/zingen.php?psalm={ps}&psvID=8"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    opts = soup.select("select[name=vers] option")
    vals = [o.get("value") for o in opts if o.get("value", "").isdigit()]
    if not vals:
        return None

    return max(int(v) for v in vals)


async def scrape_zingen(ps: int, vs: int):
    """Bron 1: zingen.php pagina"""
    url = f"https://psalmboek.nl/zingen.php?psalm={ps}&psvID={vs}"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    cont = soup.select_one("div.content") or soup
    p = cont.find("p")
    if not p:
        return None
    text = p.get_text(separator="\n", strip=True)
    return text, "psalmboek.nl/zingen.php"


async def scrape_old(ps: int, vs: int):
    """Bron 2: legacy /psalm/{ps}/vers/{vs}?berijming=1773"""
    url = f"https://psalmboek.nl/psalm/{ps:03d}/vers/{vs:02d}?berijming=1773"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    node = soup.select_one("div.verse-text")
    if not node:
        return None
    text = node.get_text(separator="\n", strip=True)
    return text, "psalmboek.nl/psalm"


async def scrape_refo(ps: int, vs: int):
    """Bron 3: Reformatorische Omroep plain-text"""
    url = f"https://content.reformatorischeomroep.nl/psalmen/berijming-1773/{ps}/{vs}.txt"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    return r.text.strip(), "reformatorischeomroep.nl"


SCRAPERS = [scrape_zingen, scrape_old, scrape_refo]


### ────────────────────────────────────
### Endpoints
### ────────────────────────────────────

@app.get(
    "/api/psalm/max",
    response_model=int,
    responses={404: {"model": Error}}
)
async def get_psalm_max(
    psalm: int = Query(..., ge=1, le=150)
):
    """Bepaalt het maximaal versnummer van Psalm X (1773)."""
    maxv = await fetch_max(psalm)
    if maxv is None:
        raise HTTPException(
            status_code=404,
            detail=f"Geen verzen gevonden voor Psalm {psalm}."
        )
    return maxv


@app.get(
    "/api/psalm",
    response_model=PsalmVers,
    responses={404: {"model": Error}}
)
async def get_berijmd_psalmvers(
    psalm: int = Query(..., ge=1, le=150),
    vers:  int = Query(..., ge=1)
):
    """Haal één berijmd psalmvers (1773) op."""
    maxv = await fetch_max(psalm)
    if maxv is None:
        raise HTTPException(status_code=404, detail=f"Psalm {psalm} niet gevonden.")
    if vers > maxv:
        raise HTTPException(status_code=404, detail=f"Vers {vers} bestaat niet, max is {maxv}.")

    for scraper in SCRAPERS:
        try:
            res = await scraper(psalm, vers)
            if res:
                text, bron = res
                return PsalmVers(psalm=psalm, vers=vers, text=text, bron=bron)
        except:
            pass

    raise HTTPException(
        status_code=404,
        detail=f"Vers {vers} van Psalm {psalm} kon niet worden opgehaald."
    )
