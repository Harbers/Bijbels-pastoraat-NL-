# main.py
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup

app = FastAPI(
    title="Bijbelse Psalmen API",
    version="1.0",
    openapi_url="/openapi.yaml",   # we serveren de spec zelf
    docs_url="/docs"               # optioneel: de Swagger UI
)

# 1) plugin‐manifest en (optionele) iconen
#    worden via de map `well-known/` geserveerd
app.mount(
    "/.well-known",
    StaticFiles(directory="well-known"),
    name="well-known"
)

class PsalmVers(BaseModel):
    psalm: int
    vers: int
    text: str

class Error(BaseModel):
    detail: str

# 2) Haal een vers op uit Psalmboek.nl (1773-berijming)
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

# 3) Lees het dropdown‐veld op zingen.php uit om max vers te bepalen
async def fetch_maxvers(ps: int) -> int | None:
    # psvID=8 is de code voor berijming=1773
    url = f"https://psalmboek.nl/zingen.php?psalm={ps}&psvID=8"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    # dropdown <select name="vers"> bevat <option value="XX">
    opts = soup.select("select[name=vers] option")
    # de eerste optie is vaak een lege instructie; dus tel de rest
    waarden = [o.get("value") for o in opts if o.get("value", "").isdigit()]
    if not waarden:
        return None
    return max(int(v) for v in waarden)

SCRAPERS = [fetch_psalmvers]

@app.get(
    "/api/psalm",
    response_model=PsalmVers,
    responses={404: {"model": Error}}
)
async def get_psalm_vers(psalm: int, vers: int):
    """Haal één berijmd psalmvers (1773)."""
    for fn in SCRAPERS:
        try:
            txt = await fn(psalm, vers)
            if txt:
                return PsalmVers(psalm=psalm, vers=vers, text=txt)
        except Exception:
            pass
    raise HTTPException(status_code=404, detail="Psalmvers niet gevonden in 1773-berijming")

@app.get(
    "/api/psalm/max",
    response_model=int,
    responses={404: {"model": Error}}
)
async def get_psalm_max(psalm: int):
    """Geef maximaal versnummer (1773-berijming)."""
    mv = await fetch_maxvers(psalm)
    if mv is not None:
        return mv
    raise HTTPException(status_code=404, detail="Psalm niet gevonden")
