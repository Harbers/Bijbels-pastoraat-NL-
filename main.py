from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup

app = FastAPI(
    title="Bijbelse Psalmen Scraper API",
    openapi_url="/openapi.yaml"
)

### ────────────────────────────────────
### Datamodellen
### ────────────────────────────────────
class PsalmMax(BaseModel):
    psalm: int
    max_vers: int

class PsalmVers(BaseModel):
    psalm: int
    vers: int
    text: str

class Error(BaseModel):
    detail: str

### ────────────────────────────────────
### OpenAPI & Plugin manifest endpoints
### ────────────────────────────────────
@app.get("/openapi.yaml", include_in_schema=False)
async def openapi_spec():
    return FileResponse("openapi.yaml")

@app.get("/ai-plugin.json", include_in_schema=False)
async def plugin_manifest():
    return FileResponse("ai-plugin.json")

### ────────────────────────────────────
###  Helper: bepaal max vers
### ────────────────────────────────────
@app.get(
    "/api/psalm/max",
    response_model=PsalmMax,
    responses={404: {"model": Error}},
    summary="Geef maximaal versnummer in 1773-berijming",
)
async def get_psalm_max(psalm: int):
    url = f"https://psalmboek.nl/psalm/{psalm:03d}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        raise HTTPException(status_code=404, detail="Psalm niet gevonden")
    soup = BeautifulSoup(r.text, "html.parser")
    # de vers-buttons staan in <nav class="versen"> als <a> met tekst=nr
    links = soup.select("nav.versen a")
    verses = [int(a.text) for a in links if a.text.isdigit()]
    if not verses:
        raise HTTPException(status_code=404, detail="Geen versregister gevonden")
    return PsalmMax(psalm=psalm, max_vers=max(verses))

### ────────────────────────────────────
###  Helper: haal vers op
### ────────────────────────────────────
@app.get(
    "/api/psalm",
    response_model=PsalmVers,
    responses={404: {"model": Error}},
    summary="Haal één berijmd psalmvers (1773)",
)
async def get_psalm_vers(psalm: int, vers: int):
    # valideer eerst tegen het max-vers endpoint
    max_data = await get_psalm_max(psalm)
    if vers < 1 or vers > max_data.max_vers:
        raise HTTPException(
            status_code=404,
            detail=f"Vers {vers} bestaat niet (max is {max_data.max_vers})"
        )
    url = f"https://psalmboek.nl/psalm/{psalm:03d}/vers/{vers:02d}?berijming=1773"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        raise HTTPException(status_code=404, detail="Psalmvers niet gevonden")
    soup = BeautifulSoup(r.text, "html.parser")
    stanza = soup.select_one("div.verse-text")
    if not stanza:
        raise HTTPException(status_code=404, detail="Tekst niet gevonden")
    # behoud originele linebreaks
    text = "\n".join(line.strip() for line in stanza.get_text("\n").splitlines() if line.strip())
    return PsalmVers(psalm=psalm, vers=vers, text=text)
