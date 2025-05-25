# main.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup

app = FastAPI(
    title="Bijbelse Psalmen API",
    version="1.0",
    openapi_url="/openapi.yaml",   # serveer de OpenAPI-spec hier
    docs_url="/docs"               # optioneel: Swagger UI op /docs
)

# 1) plugin-manifest en eventuele iconen in .well-known/
app.mount(
    "/.well-known",
    StaticFiles(directory="well-known", html=False),
    name="well-known"
)

# Data-modellen
class PsalmVers(BaseModel):
    psalm: int
    vers: int
    text: str

class Error(BaseModel):
    detail: str

# Scraper-functies (gebruik je bestaande implementatie)
async def fetch_psalmvers(ps: int, vs: int) -> str | None:
    url = f"https://psalmboek.nl/psalm/{ps:03d}/vers/{vs:02d}?berijming=1773"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    node = soup.select_one("div.verse-text")
    return node.get_text(strip=True) if node else None

async def fetch_maxvers(ps: int) -> int | None:
    url = f"https://psalmboek.nl/zingen.php?psalm={ps}&psvID=8"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    opts = soup.select("select[name=vers] option")
    waarden = [o.get("value") for o in opts if o.get("value", "").isdigit()]
    if not waarden:
        return None
    return max(int(v) for v in waarden)

SCRAPERS = [fetch_psalmvers]

# 2) Route voor één vers
@app.get(
    "/api/psalm",
    response_model=PsalmVers,
    responses={404: {"model": Error}}
)
async def get_psalm_vers(
    psalm: int = Query(..., ge=1, le=150, description="Psalmnummer (1–150)"),
    vers:  int = Query(..., ge=1, description="Versnummer")
):
    for fn in SCRAPERS:
        try:
            txt = await fn(psalm, vers)
            if txt:
                return PsalmVers(psalm=psalm, vers=vers, text=txt)
        except Exception:
            continue
    raise HTTPException(status_code=404, detail="Psalmvers niet gevonden in 1773-berijming")

# 3) Route voor max-vers
@app.get(
    "/api/psalm/max",
    response_model=int,
    responses={404: {"model": Error}}
)
async def get_psalm_max(
    psalm: int = Query(..., ge=1, le=150, description="Psalmnummer (1–150)")
):
    mv = await fetch_maxvers(psalm)
    if mv is not None:
        return mv
    raise HTTPException(status_code=404, detail="Psalm niet gevonden")

# 4) (Optioneel) serveer de YAML-file exact zoals je ‘m hebt
@app.get("/openapi.yaml", include_in_schema=False)
async def openapi_spec():
    return FileResponse("openapi.yaml", media_type="application/yaml")
