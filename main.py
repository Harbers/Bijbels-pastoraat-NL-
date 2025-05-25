from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup

app = FastAPI()

### ────────────────────────────────────
###  Datamodellen
### ────────────────────────────────────
class PsalmVers(BaseModel):
    psalm: int
    vers: int
    text: str

class Error(BaseModel):
    detail: str

### ────────────────────────────────────
###  Scraping-helpers
### ────────────────────────────────────
async def fetch_psalmboek(ps, vs):
    """
    Bron 1 – psalmboek.nl
    URL-patroon: https://psalmboek.nl/psalm/{ps:03d}/vers/{vs:02d}?berijming=1773
    """
    url = f"https://psalmboek.nl/psalm/{ps:03d}/vers/{vs:02d}?berijming=1773"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    stanza = soup.select_one("div.verse-text")
    return stanza.get_text(strip=True) if stanza else None


async def fetch_onlinebijbel(ps, vs):
    """
    Bron 2 – online-bijbel.org
    De site groepeert coupletten anders; daarom zoeken we op de eerste regel.
    """
    firstline = {
        8: "Gelijk het gras is ons kortstondig leven",
    }.get(vs)
    if not firstline:
        return None
    url = f"https://www.online-bijbel.nl/psalmen-1773/{ps}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    if firstline in r.text:
        #   ruwe, maar snelle extractie
        start = r.text.find(firstline)
        end = r.text.find("<br/>", start)
        return BeautifulSoup(r.text[start:end], "html.parser").get_text(strip=True)
    return None


async def fetch_ro(ps, vs):
    """
    Bron 3 – Reformatorische Omroep (plain-text index)
    """
    url = f"https://content.reformatorischeomroep.nl/psalmen/berijming-1773/{ps}/{vs}.txt"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    return r.text.strip() if r.status_code == 200 else None


SCRAPE_SOURCES = [fetch_psalmboek, fetch_onlinebijbel, fetch_ro]

### ────────────────────────────────────
###  API-route
### ────────────────────────────────────
@app.get(
    "/api/debug/vers",
    response_model=PsalmVers,
    responses={"404": {"model": Error}},
)
async def get_berijmd_psalmvers(psalm: int, vers: int):
    """
    Zoekt het gevraagde vers achtereenvolgens in drie openbare bronnen.
    Wordt nergens een resultaat gevonden → 404.
    """
    for fn in SCRAPE_SOURCES:
        try:
            if (txt := await fn(psalm, vers)):
                return PsalmVers(psalm=psalm, vers=vers, text=txt)
        except Exception:
            #  Bron onbereikbaar?  We proberen stilzwijgend de volgende.
            continue
    raise HTTPException(status_code=404, detail="Psalmvers niet gevonden in 1773-berijming")
