from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup

app = FastAPI()

class PsalmVers(BaseModel):
    psalm: int
    vers: int
    text: str

class Error(BaseModel):
    detail: str

### Scrape één vers uit drie bronnen, in volgorde:
async def fetch_psalmboek(ps: int, vs: int) -> str | None:
    url = f"https://psalmboek.nl/psalm/{ps:03d}/vers/{vs:02d}?berijming=1773"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    el = soup.select_one("div.verse-text")
    return el.get_text(strip=True) if el else None

async def fetch_onlinebijbel(ps: int, vs: int) -> str | None:
    url = f"https://www.online-bijbel.nl/psalmen-1773/{ps}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    # eenvoudige tekst-matching op eerste regel van vers
    # (uit te breiden met dynamische lookup)
    lookup = {
        8: "Gelijk het gras is ons kortstondig leven"
    }.get(vs)
    if not lookup or lookup not in r.text:
        return None
    start = r.text.find(lookup)
    end = r.text.find("<br/>", start)
    return BeautifulSoup(r.text[start:end], "html.parser").get_text(strip=True)

async def fetch_reformatorisch(ps: int, vs: int) -> str | None:
    url = f"https://content.reformatorischeomroep.nl/psalmen/berijming-1773/{ps}/{vs}.txt"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    return r.text.strip() if r.status_code == 200 else None

SCRAPE_SOURCES = [fetch_psalmboek, fetch_onlinebijbel, fetch_reformatorisch]

@app.get(
    "/api/psalm",
    response_model=PsalmVers,
    responses={400: {"model": Error}, 404: {"model": Error}},
)
async def getPsalmVers(
    psalm: int = Query(..., ge=1, le=150),
    vers: int = Query(..., ge=1),
):
    # valideer via max-endpoint
    # (gebruik /api/psalm/max onder de motorkap)
    # hier optioneel: fetch Psalm Max en raise 400 bij te groot vers
    # …
    for fn in SCRAPE_SOURCES:
        try:
            text = await fn(psalm, vers)
            if text:
                return PsalmVers(psalm=psalm, vers=vers, text=text)
        except Exception:
            continue
    raise HTTPException(status_code=404, detail="Psalmvers niet gevonden")

@app.get(
    "/api/psalm/max",
    response_model=dict,
    responses={404: {"model": Error}},
)
async def getPsalmMax(
    psalm: int = Query(..., ge=1, le=150),
):
    # scrape hoofdstuk-index op psalmboek.nl
    url = f"https://psalmboek.nl/psalm/{psalm:03d}?berijming=1773"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        raise HTTPException(status_code=404, detail="Psalm niet gevonden")
    soup = BeautifulSoup(r.text, "html.parser")
    # links naar elk vers bevatten “/vers/NN”
    verses = []
    for a in soup.select("div.chapter-list a[href*='/vers/']"):
        href = a["href"]
        try:
            num = int(href.split("/vers/")[-1].split("?")[0])
            verses.append(num)
        except ValueError:
            continue
    if not verses:
        raise HTTPException(status_code=404, detail="Geen verzen gevonden")
    return {"psalm": psalm, "max_vers": max(verses)}
