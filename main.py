from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup

app = FastAPI(
    title="Bijbelse Psalmen API",
    version="1.0",
    openapi_url=None,        # serve spec manually
    docs_url="/docs"
)

# Serve plugin manifest & logo
app.mount(
    "/.well-known",
    StaticFiles(directory=".well-known", html=False),
    name="well-known"
)

# Serve OpenAPI spec
@app.get("/openapi.yaml", include_in_schema=False)
async def openapi_spec():
    return FileResponse("openapi.yaml", media_type="application/x-yaml")

# Models
class PsalmVers(BaseModel):
    psalm: int
    vers: int
    text: str
    bron: str

class Error(BaseModel):
    detail: str

# Helper: fetch max vers
async def fetch_max(ps: int) -> int | None:
    url = f"https://psalmboek.nl/zingen.php?psalm={ps}&psvID=8"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    opts = soup.select("select[name=vers] option")
    vals = [o.get("value") for o in opts if o.get("value", "").isdigit()]
    return max(map(int, vals)) if vals else None

# Scrapers
async def fetch_zingen(ps: int, vs: int):
    url = f"https://psalmboek.nl/zingen.php?psalm={ps}&psvID={vs}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    p = (soup.select_one("div.content") or soup).find("p")
    if not p: return None
    return p.get_text(separator="\n", strip=True), "psalmboek.nl/zingen.php"

async def fetch_old(ps: int, vs: int):
    url = f"https://psalmboek.nl/psalm/{ps:03d}/vers/{vs:02d}?berijming=1773"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200: return None
    node = BeautifulSoup(r.text, "html.parser").select_one("div.verse-text")
    if not node: return None
    return node.get_text(separator="\n"), "psalmboek.nl/psalm"

async def fetch_ro(ps: int, vs: int):
    url = f"https://content.reformatorischeomroep.nl/psalmen/berijming-1773/{ps}/{vs}.txt"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200: return None
    return r.text, "reformatorischeomroep.nl"

SCRAPERS = [fetch_zingen, fetch_old, fetch_ro]

# Routes
@app.get(
    "/api/debug/vers",
    response_model=PsalmVers,
    responses={404: {"model": Error}}
)
async def get_berijmd_psalmvers(
    psalm: int = Query(..., ge=1, le=150),
    vers:  int = Query(..., ge=1)
):
    # Validate vers against max
    maxv = await fetch_max(psalm)
    if maxv is None:
        raise HTTPException(status_code=404, detail=f"Psalm {psalm} niet gevonden.")
    if vers > maxv:
        raise HTTPException(status_code=404, detail=f"Vers {vers} bestaat niet, max is {maxv}.")
    # Scrape
    for fn in SCRAPERS:
        try:
            res = await fn(psalm, vers)
            if res:
                text, bron = res
                return PsalmVers(psalm=psalm, vers=vers, text=text, bron=bron)
        except:
            continue
    raise HTTPException(status_code=404, detail=f"Vers {vers} van Psalm {psalm} kon niet worden opgehaald.")

@app.get(
    "/api/psalm/max",
    response_model=int,
    responses={404: {"model": Error}}
)
async def get_psalm_max(psalm: int = Query(..., ge=1, le=150)):
    maxv = await fetch_max(psalm)
    if maxv is None:
        raise HTTPException(status_code=404, detail=f"Psalm {psalm} niet gevonden.")
    return maxv
