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
    openapi_url=None,      # we serveren de spec zelf
    docs_url="/docs"
)

# 1) Plugin‐manifest en iconen in .well-known/
app.mount(
    "/.well-known",
    StaticFiles(directory=".well-known", html=False),
    name="well-known"
)

# 2) OpenAPI-spec zelf serveren
@app.get("/openapi.yaml", include_in_schema=False)
async def serve_openapi():
    return FileResponse("openapi.yaml", media_type="application/x-yaml")


### ────────────────────────────────────
### Datamodellen
### ────────────────────────────────────
class PsalmVers(BaseModel):
    psalm: int
    vers: int
    text: str
    bron: str

class Error(BaseModel):
    detail: str


### ────────────────────────────────────
### Helper: Bepaal maximaal versnummer
### ────────────────────────────────────
async def fetch_max(ps: int) -> int | None:
    """
    Haal het hoogste versnummer op van de 1773-berijming via zingen.php?psvID=8
    """
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


### ────────────────────────────────────
### Scrapers (volgorde van prioriteit)
### ────────────────────────────────────
async def fetch_zingen(ps: int, vs: int):
    """
    Bron 1 – psalmboek.nl via zingen.php-pagina
    """
    url = f"https://psalmboek.nl/zingen.php?psalm={ps}&psvID={vs}"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    # kies eerste <p> binnen div.content
    container = soup.select_one("div.content") or soup
    p = container.find("p")
    if not p:
        return None

    tekst = p.get_text(separator="\n", strip=True)
    return tekst, "psalmboek.nl/zingen.php"


async def fetch_old(ps: int, vs: int):
    """
    Bron 2 – psalmboek.nl via legacy URL met berijming=1773
    """
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

    tekst = node.get_text(separator="\n", strip=True)
    return tekst, "psalmboek.nl/psalm"


async def fetch_reformatorischeomroep(ps: int, vs: int):
    """
    Bron 3 – Reformatorische Omroep plain-text index
    """
    url = f"https://content.reformatorischeomroep.nl/psalmen/berijming-1773/{ps}/{vs}.txt"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None

    tekst = r.text.strip()
    return tekst, "reformatorischeomroep.nl"


SCRAPERS = [
    fetch_zingen,
    fetch_old,
    fetch_reformatorischeomroep,
]


### ────────────────────────────────────
### API-Endpoints
### ────────────────────────────────────
@app.get(
    "/api/debug/vers",
    response_model=PsalmVers,
    responses={404: {"model": Error}}
)
async def get_berijmd_psalmvers(
    psalm: int = Query(..., ge=1, le=150),
    vers:  int = Query(..., ge=1)
):
    # 1) Controle max vers
    maxv = await fetch_max(psalm)
    if maxv is None:
        raise HTTPException(status_code=404, detail=f"Psalm {psalm} niet gevonden.")
    if vers > maxv:
        raise HTTPException(
            status_code=404,
            detail=f"Vers {vers} bestaat niet, max is {maxv}."
        )

    # 2) Scrape in volgorde
    for fn in SCRAPERS:
        try:
            res = await fn(psalm, vers)
            if res:
                text, bron = res
                return PsalmVers(psalm=psalm, vers=vers, text=text, bron=bron)
        except Exception:
            continue

    # 3) Niet gevonden
    raise HTTPException(
        status_code=404,
        detail=f"Vers {vers} van Psalm {psalm} kon niet worden opgehaald."
    )


@app.get(
    "/api/psalm/max",
    response_model=int,
    responses={404: {"model": Error}}
)
async def get_psalm_max(
    psalm: int = Query(..., ge=1, le=150)
):
    maxv = await fetch_max(psalm)
    if maxv is None:
        raise HTTPException(status_code=404, detail=f"Geen verzen gevonden voor Psalm {psalm}.")
    return maxv
