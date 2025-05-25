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
async def fetch_psalmboek_zingen(ps: int, vs: int):
    """
    Bron 1 – psalmboek.nl via de zingen.php-pagina
    URL-patroon: https://psalmboek.nl/zingen.php?psalm={ps}&psvID={vs}
    Deze pagina toont *alle* verzen en geeft het gevraagde vers weer.
    """
    url = f"https://psalmboek.nl/zingen.php?psalm={ps}&psvID={vs}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    # daar waar de tekst in een <p> staat direct onder de titel "Psalm X vers Y"
    # in de praktijk zit dit in een container met class "content" of "page"
    # we proberen een generieke <p> onder de header te pakken:
    #  * eerst binnen div.met class "content", zo niet, fallback op eerste <p>
    container = soup.select_one("div.content") or soup
    p = container.find("p")
    return p.get_text(strip=True) if p else None


async def fetch_psalmboek_old(ps: int, vs: int):
    """
    Bron 2 – psalmboek.nl via de verse-echte URL (werkt soms alleen t/m 7)
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


async def fetch_onlinebijbel(ps: int, vs: int):
    """
    Bron 3 – online-bijbel.nl (1773-berijming)
    Werkt alleen als we de eerste regel kennen; beperkt.
    """
    firstline_map = {
        # voeg hier per vers de startregel toe
        8: "Gelijk het gras is ons kortstondig leven",
        # …
    }
    firstline = firstline_map.get(vs)
    if not firstline:
        return None

    url = f"https://www.online-bijbel.nl/psalmen-1773/{ps}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200 or firstline not in r.text:
        return None

    start = r.text.find(firstline)
    end = r.text.find("<br/>", start)
    return BeautifulSoup(r.text[start:end], "html.parser").get_text(strip=True)


async def fetch_reformatorischeomroep(ps: int, vs: int):
    """
    Bron 4 – Reformatorische Omroep (plain-text index)
    URL-patroon: https://content.reformatorischeomroep.nl/psalmen/berijming-1773/{ps}/{vs}.txt
    """
    url = f"https://content.reformatorischeomroep.nl/psalmen/berijming-1773/{ps}/{vs}.txt"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    return r.text.strip() if r.status_code == 200 else None


# Prioriteit: eerst de nieuwe zingen.php-scraper, dan de oude, etc.
SCRAPE_SOURCES = [
    fetch_psalmboek_zingen,
    fetch_psalmboek_old,
    fetch_onlinebijbel,
    fetch_reformatorischeomroep,
]

### ────────────────────────────────────
###  API-route
### ────────────────────────────────────
@app.get(
    "/api/debug/vers",
    response_model=PsalmVers,
    responses={404: {"model": Error}},
)
async def get_berijmd_psalmvers(psalm: int, vers: int):
    """
    Zoekt het gevraagde vers (in de 1773-berijming) achtereenvolgens
    in vier openbare bronnen. Zodra er één iets oplevert, stoppen we.
    """
    for scraper in SCRAPE_SOURCES:
        try:
            if (tekst := await scraper(psalm, vers)):
                return PsalmVers(psalm=psalm, vers=vers, text=tekst)
        except Exception:
            # bron onbereikbaar → probeer de volgende
            continue

    # niets gevonden
    raise HTTPException(
        status_code=404,
        detail=f"Psalm {psalm}:{vers} niet gevonden in de 1773-berijming"
    )
