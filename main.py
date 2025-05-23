"""FastAPI‑backend voor berijmde psalmen 1773
------------------------------------------------
Scrapet uitsluitend **psalmboek.nl** en levert:
*  /api/psalm/max  → maximaal versnummer (berijmd)
*  /api/psalm      → exacte, ongewijzigde vers‑tekst
*  /debug/versen   → lijst versnummers (voor snelle check)

Robuuste detectie:
– zoekt naar alle patronen `psalm={nummer}&psvID={vers}` in de HTML; dat
  zijn de links die uitsluitend naar berijmde verzen verwijzen.
– Regex‑benadering werkt zelfs wanneer de HTML‑structuur (div / a / select)
  later cosmetisch wijzigt.
"""

from __future__ import annotations

import re
import logging
from functools import lru_cache

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, APIRouter, HTTPException, Query

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
router = APIRouter(prefix="/api")

###############################################################################
# 1.  HTTP‑hulp
###############################################################################

@lru_cache(maxsize=512)
def _http_get(url: str) -> str:
    """Ophalen met simpele headers + caching."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; PsalmScraper/1.0)",
        "Accept-Language": "nl-NL,nl;q=0.9",
    }
    resp = requests.get(url, headers=headers, timeout=12)
    if resp.status_code == 200:
        return resp.text
    raise HTTPException(resp.status_code, f"Fout bij ophalen {url}")

###############################################################################
# 2.  Bepaal maximaal versnummer (berijmd)
###############################################################################

@lru_cache(maxsize=150)
def get_max_berijmd_vers(psalm: int) -> int:
    """Zoek alle patronen …psalm={psalm}&psvID={vers}… en neem max(vers)."""
    url = f"https://psalmboek.nl/zingen.php?psalm={psalm}"
    html = _http_get(url)

    # Regex is minder gevoelig dan CSS‑select wanneer de layout wijzigt.
    hits = {int(m) for m in re.findall(rf"psalm={psalm}&psvID=(\d+)", html)}

    if not hits:
        raise HTTPException(404, f"Geen berijmde verzen gevonden voor psalm {psalm}.")

    hoogste = max(hits)
    logger.info("Psalm %d → %d verzen", psalm, hoogste)
    return hoogste

###############################################################################
# 3.  Vers‑tekst ophalen
###############################################################################

def _extract_vers_psalmboek(psalm: int, vers: int) -> str:
    url = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID={vers}#psvs"
    soup = BeautifulSoup(_http_get(url), "html.parser")
    blok = soup.find("div", id="psvs")
    if blok:
        return blok.get_text("\n", strip=True)
    raise HTTPException(404, "Vers niet gevonden bij psalmboek.nl")

###############################################################################
# 4.  API‑endpoints
###############################################################################

@router.get("/psalm/max")
def api_psalm_max(psalm: int = Query(..., ge=1, le=150)):
    return {"psalm": psalm, "max_vers": get_max_berijmd_vers(psalm)}


@router.get("/psalm")
def api_psalm(
    psalm: int = Query(..., ge=1, le=150),
    vers: int = Query(..., ge=1),
):
    max_vers = get_max_berijmd_vers(psalm)
    if vers > max_vers:
        raise HTTPException(400, f"Psalm {psalm} heeft slechts {max_vers} verzen.")
    tekst = _extract_vers_psalmboek(psalm, vers)
    return {"psalm": psalm, "vers": vers, "tekst": tekst}

###############################################################################
# 5.  Debug‑route – toont gevonden versnummers
###############################################################################

@app.get("/debug/versen")
def debug_versen(psalm: int):
    url = f"https://psalmboek.nl/zingen.php?psalm={psalm}"
    html = _http_get(url)
    hits = sorted({int(m) for m in re.findall(rf"psalm={psalm}&psvID=(\d+)", html)})
    return {"psalm": psalm, "verzen": hits}

###############################################################################
# 6.  Root + router
###############################################################################

@app.get("/")
def root():
    return {"status": "Psalm‑API actief (berijmd 1773)"}

app.include_router(router)
