from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import httpx
from bs4 import BeautifulSoup

app = FastAPI(
    title="Bijbelse Psalmen Scraper API",
    openapi_url="/openapi.yaml",
    docs_url=None,
    redoc_url=None
)

# 1) Serveer alleen de plugin-manifest (en evt. logo) onder /.well-known
app.mount(
    "/.well-known",
    StaticFiles(directory=".well-known", html=False),
    name="well-known"
)

# 2) (optioneel) logo serve
app.mount("/logo.png", StaticFiles(directory=".", html=False), name="logo")

# 3) CORS als ChatGPT dat eist
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

### ────────────────────────────────────
class PsalmVers(BaseModel):
    psalm: int
    vers: int
    text: str

class Error(BaseModel):
    detail: str

### ────────────────────────────────────
# Scrapers (kopieer hier je werkende helpers)
async def fetch_psalmboek(ps, vs):
    url = f"https://psalmboek.nl/zingen.php?psalm={ps}&psvID={vs}&berijming=1773"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    # elk regel is <p class="verse"> of zo; pas selector aan
    lines = [p.get_text(strip=True) for p in soup.select("div.verse-text p")]
    return "\n".join(lines) if lines else None

async def fetch_ro(ps, vs):
    url = f"https://content.reformatorischeomroep.nl/psalmen/berijming-1773/{ps}/{vs}.txt"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    return r.text.strip() if r.status_code == 200 else None

SCRAPE_SOURCES = [fetch_psalmboek, fetch_ro]

### ────────────────────────────────────
@app.get("/api/psalm/max", response_model=int, responses={404: {"model": Error}})
async def get_psalm_max(psalm: int):
    # eenvoudige fallbacklijst of bereken via onlinebron
    # bijvoorbeeld Reformatorische Omroep index: psalmboek.nl toont tot 11 voor psalm 103
    # Hier hardcode als voorbeeld:
    dummy_max = {103: 11}
    if psalm in dummy_max:
        return dummy_max[psalm]
    raise HTTPException(status_code=404, detail="Psalm niet gevonden")

@app.get("/api/psalm", response_model=PsalmVers, responses={404: {"model": Error}})
async def get_psalm_vers(psalm: int, vers: int):
    # 1) check max
    max_vers = await get_psalm_max(psalm)
    if vers < 1 or vers > max_vers:
        raise HTTPException(
            status_code=404,
            detail=f"Psalm {psalm}:{vers} bestaat niet (max is {max_vers})"
        )
    # 2) probeer elke bron
    for fetch in SCRAPE_SOURCES:
        try:
            txt = await fetch(psalm, vers)
            if txt:
                return PsalmVers(psalm=psalm, vers=vers, text=txt)
        except:
            pass
    raise HTTPException(status_code=404, detail="Psalmvers niet gevonden in 1773-berijming")

# serveer OpenAPI spec
@app.get("/openapi.yaml", include_in_schema=False)
async def openapi_spec():
    return StaticFiles(directory=".", html=False)
