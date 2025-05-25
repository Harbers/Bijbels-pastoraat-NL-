from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup

app = FastAPI(
    title="Bijbelse Psalmen Scraper API",
    version="1.0",
    description="Haal berijmde psalmverzen op uit drie online bronnen (1773-berijming)."
)

# 1) Serve .well-known voor de GPT-plugin
app.mount(
    "/.well-known",
    StaticFiles(directory=".well-known"),
    name="well-known",
)

### ────────────────────────────────────
### Datamodellen
### ────────────────────────────────────
class PsalmVers(BaseModel):
    psalm: int
    vers: int
    text: str

class Error(BaseModel):
    detail: str

### ────────────────────────────────────
### Scraping-helpers
### ────────────────────────────────────
async def fetch_psalmboek(ps: int, vs: int) -> str | None:
    url = f"https://psalmboek.nl/psalm/{ps:03d}/vers/{vs:02d}?berijming=1773"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    node = soup.select_one("div.verse-text")
    return node.get_text(strip=True) if node else None

async def fetch_onlinebijbel(ps: int, vs: int) -> str | None:
    # deze site toont alle verzen achter elkaar; we zoeken op "<versnummer>. " en knippen bij de volgende <br>
    url = f"https://www.online-bijbel.nl/psalmen-1773/{ps}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None

    marker = f"{vs}. "
    idx = r.text.find(marker)
    if idx == -1:
        return None
    # vind het volgende <br> na de marker
    start = idx + len(marker)
    end = r.text.find("<br/>", start)
    snippet = r.text[start:end]
    return BeautifulSoup(snippet, "html.parser").get_text(strip=True)

async def fetch_ro(ps: int, vs: int) -> str | None:
    url = f"https://content.reformatorischeomroep.nl/psalmen/berijming-1773/{ps}/{vs}.txt"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    return r.text.strip() if r.status_code == 200 else None

SCRAPE_SOURCES = [fetch_psalmboek, fetch_onlinebijbel, fetch_ro]

### ────────────────────────────────────
### Hulpfunctie voor maximaal versnummer
### ────────────────────────────────────
async def get_max_vers(ps: int) -> int:
    """
    Haal dynamisch het aantal verzen op bij Psalmboek.
    """
    url = f"https://psalmboek.nl/psalm/{ps:03d}?berijming=1773"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        raise HTTPException(status_code=404, detail=f"Psalm {ps} niet gevonden")
    soup = BeautifulSoup(r.text, "html.parser")
    verses = soup.select("div.verse-text")
    if not verses:
        raise HTTPException(status_code=404, detail=f"Psalm {ps} heeft geen verzen in 1773-berijming")
    return len(verses)

### ────────────────────────────────────
### API-routes
### ────────────────────────────────────
@app.get(
    "/api/psalm",
    response_model=PsalmVers,
    responses={"404": {"model": Error}, "400": {"model": Error}},
    summary="Haal één berijmd psalmvers (1773)"
)
async def get_psalm_vers(
    psalm: int = Query(..., ge=1, le=150, description="Psalmnummer (1–150)"),
    vers:  int = Query(..., ge=1, description="Versnummer")
):
    # valideer dat vers binnen de range valt
    max_vers = await get_max_vers(psalm)
    if vers > max_vers:
        raise HTTPException(
            status_code=400,
            detail=f"Psalm {psalm} heeft maximaal {max_vers} verzen, gevraagd {vers}."
        )

    # probeer elke bron
    for fetch in SCRAPE_SOURCES:
        try:
            text = await fetch(psalm, vers)
            if text:
                return PsalmVers(psalm=psalm, vers=vers, text=text)
        except Exception:
            # als één bron faalt, probeer de volgende
            continue

    # niets gevonden
    raise HTTPException(status_code=404, detail="Psalmvers niet gevonden in 1773-berijming")


@app.get(
    "/api/psalm/max",
    response_model=int,
    responses={"404": {"model": Error}},
    summary="Geef maximaal versnummer in 1773-berijming"
)
async def api_get_psalm_max(
    psalm: int = Query(..., ge=1, le=150, description="Psalmnummer (1–150)")
):
    return await get_max_vers(psalm)
