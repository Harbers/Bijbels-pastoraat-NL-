from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup

app = FastAPI()

class PsalmVers(BaseModel):
    psalm: int
    vers: int
    text: str
    bron: str

class Error(BaseModel):
    detail: str

async def fetch_from_zingen(ps: int, vs: int):
    url = f"https://psalmboek.nl/zingen.php?psalm={ps}&psvID={vs}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    container = soup.select_one("div.content") or soup
    p = container.find("p")
    if not p:
        return None
    text = p.get_text(separator="\n", strip=True)
    return text, "psalmboek.nl/zingen.php"

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
    text = stanza.get_text(separator="\n", strip=True)
    return text, "psalmboek.nl/psalm/{ps:03d}/vers/{vs:02d}"

async def fetch_from_refo(ps: int, vs: int):
    url = f"https://content.reformatorischeomroep.nl/psalmen/berijming-1773/{ps}/{vs}.txt"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    text = r.text.strip()
    if not text:
        return None
    return text, "content.reformatorischeomroep.nl"

SCRAPERS = [
    fetch_from_zingen,
    fetch_from_old,
    fetch_from_refo,
]

@app.get(
    "/api/psalm",
    response_model=PsalmVers,
    responses={404: {"model": Error}},
)
async def get_psalm_vers(
    psalm: int = Query(..., ge=1, le=150),
    vers: int = Query(..., ge=1)
):
    """
    Haal één berijmd psalmvers (1773) op uit meerdere bronnen.
    """
    for scraper in SCRAPERS:
        try:
            result = await scraper(psalm, vers)
            if result:
                text, bron = result
                return PsalmVers(psalm=psalm, vers=vers, text=text, bron=bron)
        except Exception:
            continue

    raise HTTPException(
        status_code=404,
        detail=f"Vers {vers} van Psalm {psalm} kon niet worden opgehaald."
    )

@app.get(
    "/api/psalm/max",
    response_model=int,
    responses={404: {"model": Error}},
)
async def get_psalm_max(
    psalm: int = Query(..., ge=1, le=150)
):
    """
    Bepaal het maximaal versnummer van een psalm in de 1773-berijming.
    """
    # We proberen de zingen.php-pagina met psvID=0 te vragen: die geeft een lijst van alle verzen
    url = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID=0"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        raise HTTPException(
            status_code=404,
            detail=f"Psalm {psalm} niet gevonden."
        )
    soup = BeautifulSoup(r.text, "html.parser")
    # Zoek alle opties in de vers-select (naam psvID)
    opts = soup.select("select[name=psvID] option")
    waarden = [opt.get("value") for opt in opts if opt.get("value").isdigit()]
    if not waarden:
        raise HTTPException(
            status_code=404,
            detail=f"Geen verzen gevonden voor Psalm {psalm}."
        )
    max_vers = max(int(v) for v in waarden)
    return max_vers
