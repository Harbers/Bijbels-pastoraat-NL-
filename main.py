"""FastAPI‑backend voor berijmde psalmteksten (1773)
====================================================
Scrapet **psalmboek.nl** en levert:
* `/api/psalm/max`  → hoogste berijmde versnummer
* `/api/psalm`      → letterlijke vers‑tekst
* `/debug/versen`   → snelle controle van gedetecteerde verzen

Belangrijkste wijziging
----------------------
De vers‐detector werkt nu met **regex** over de ruwe HTML in plaats van met
fragiele CSS‑selectoren. Hij zoekt naar patronen:

```
psalm=<nummer>&psvID=<vers>
```

Deze combinatie komt uitsluitend voor in de links rechtsboven – de
berijmde‑versnavigatie. Hij kan dus niet per ongeluk het raster van
psalmnummers treffen.
"""

import re
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, APIRouter, HTTPException, Query
from functools import lru_cache
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("psalm_api")

app = FastAPI()
api_router = APIRouter(prefix="/api")

# ---------------------------------------------------------------------------
#  Hulp: HTTP‑cache
# ---------------------------------------------------------------------------

@lru_cache(maxsize=256)
def cached_get(url: str) -> str:
    """Haalt een URL op met basis‑headers en korte timeout, met LRU‑cache."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "nl-NL,nl;q=0.9",
    }
    resp = requests.get(url, headers=headers, timeout=10)
    if resp.status_code != 200:
        raise HTTPException(resp.status_code, f"Fout bij ophalen {url}")
    return resp.text

# ---------------------------------------------------------------------------
#  Kern: aantal verzen bepalen via regex
# ---------------------------------------------------------------------------

VERZEN_REGEX = re.compile(r"psalm=(?P<ps>\d+)&psvID=(?P<vers>\d+)")

@lru_cache(maxsize=150)
def get_max_berijmd_vers(psalm: int) -> int:
    """Geeft hoogste berijmde versnummer voor *psalm*.

    We zoeken naar alle hyperlinks waarin zowel het gevraagde psalmnummer
    (psalm=123) als een psvID‑parameter voorkomen. Dat zijn **alleen** de
    berijmde verslinks.
    """
    url  = f"https://psalmboek.nl/zingen.php?psalm={psalm}"
    html = cached_get(url)

    matches = {
        int(m.group("vers"))
        for m in VERZEN_REGEX.finditer(html)
        if int(m.group("ps")) == psalm
    }
    if not matches:
        raise HTTPException(404, f"Geen berijmde verzen gevonden voor Psalm {psalm}.")

    max_vers = max(matches)
    logger.info("Psalm %d → %d verzen (berijmd)", psalm, max_vers)
    return max_vers

# ---------------------------------------------------------------------------
#  Vers‑tekst ophalen
# ---------------------------------------------------------------------------

def extract_vers_psalmboek(psalm: int, vers: int) -> str:
    url  = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID={vers}#psvs"
    html = cached_get(url)
    soup = BeautifulSoup(html, "html.parser")
    blok = soup.find("div", id="psvs")
    if not blok:
        raise HTTPException(404, "Vers niet gevonden (HTML‑structuur gewijzigd?)")
    return blok.get_text("\n", strip=True)

# ---------------------------------------------------------------------------
#  API‑endpoints
# ---------------------------------------------------------------------------

@api_router.get("/psalm/max")
def max_endpoint(psalm: int = Query(..., ge=1, le=150)):
    return {"psalm": psalm, "max_vers": get_max_berijmd_vers(psalm)}

@api_router.get("/psalm")
def psalm_endpoint(
    psalm: int = Query(..., ge=1, le=150),
    vers:  int = Query(..., ge=1),
):
    max_vers = get_max_berijmd_vers(psalm)
    if vers > max_vers:
        raise HTTPException(400, f"Psalm {psalm} heeft slechts {max_vers} verzen.")
    tekst = extract_vers_psalmboek(psalm, vers)
    return {"psalm": psalm, "vers": vers, "tekst": tekst}

# ---------------------------------------------------------------------------
#  Debug‑route
# ---------------------------------------------------------------------------

@app.get("/debug/versen")
def debug_versen(psalm: int):
    url  = f"https://psalmboek.nl/zingen.php?psalm={psalm}"
    html = cached_get(url)
    matches = [int(m.group("vers")) for m in VERZEN_REGEX.finditer(html) if int(m.group("ps")) == psalm]
    return {"gevonden_versen": sorted(matches)}

# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {"status": "Psalm‑API actief (berijming 1773)"}

app.include_router(api_router)
