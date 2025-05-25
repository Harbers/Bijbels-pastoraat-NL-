from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup

app = FastAPI(
    title="Bijbelse Psalmen API",
    version="1.0",
    description="Haal psalmverzen op uit de berijming van 1773 en bepaal automatisch het maximale aantal verzen per psalm."
)

# Serveer alles in .well-known (openapi.yaml, ai-plugin.json, icon.png, etc.)
app.mount(
    "/.well-known",
    StaticFiles(directory=".well-known", html=False),
    name="well-known",
)

class PsalmVers(BaseModel):
    psalm: int
    vers: int
    text: str

class Error(BaseModel):
    detail: str

# --- scrapers voor vers‐tekst ---
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
    # voorbeeld‐implementatie, alleen enkele eerste regels
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

async def fetch_ro(ps: int, vs: int) -> str | None:
    url = f"https://content.reformatorischeomroep.nl/psalmen/berijming-1773/{ps}/{vs}.txt"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    return r.text.strip() if r.status_code == 200 else None

SCRAPE_SOURCES = [fetch_psalmboek, fetch_onlinebijbel, fetch_ro]


# --- endpoint: één vers opvragen ---
@app.get(
    "/api/psalm",
    response_model=PsalmVers,
    responses={404: {"model": Error}},
    operation_id="get_psalm_vers",
    summary="Haal één berijmd psalmvers (1773)"
)
async def get_psalm_vers(
    psalm: int = Query(..., ge=1, le=150, description="Psalmnummer (1–150)"),
    vers: int  = Query(..., ge=1, description="Versnummer")
):
    # probeer elk van de scrapers
    for scraper in SCRAPE_SOURCES:
        try:
            txt = await scraper(psalm, vers)
            if txt:
                return PsalmVers(psalm=psalm, vers=vers, text=txt)
        except Exception:
            continue

    raise HTTPException(
        status_code=404,
        detail="Psalmvers niet gevonden in 1773-berijming"
    )


# --- endpoint: maximaal versnummer dynamisch bepalen ---
@app.get(
    "/api/psalm/max",
    response_model=int,
    responses={404: {"model": Error}},
    operation_id="get_psalm_max",
    summary="Geef maximaal versnummer in 1773-berijming"
)
async def get_psalm_max(
    psalm: int = Query(..., ge=1, le=150, description="Psalmnummer (1–150)")
) -> int:
    """
    Haal de zinge‐pagina op en tel het aantal <option> in de <select id="psvID">.
    Dat is precies het aantal verzen.
    """
    url = f"https://psalmboek.nl/zingen.php?psalm={psalm}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        raise HTTPException(status_code=404, detail="Psalm niet gevonden")

    soup = BeautifulSoup(r.text, "html.parser")
    sel = soup.find("select", id="psvID")
    if not sel:
        raise HTTPException(status_code=404, detail="Psalm niet gevonden (geen psvID-selector)")

    # Tel alleen de numerieke opties
    options = sel.find_all("option")
    numeric_opts = [opt for opt in options if opt.get("value", "").isdigit()]
    if not numeric_opts:
        raise HTTPException(status_code=404, detail="Geen versnummers gevonden")

    return len(numeric_opts)
