"""main.py – FastAPI‑backend voor berijmde psalmen 1773
=====================================================

* `/api/psalm/max` – hoogste beschikbare vers (berijmd)
* `/api/psalm`     – letterlijke tekst van één berijmd vers
* `/debug/versen`  – lijst gedetecteerde versnummers (debug)
* `/debug/vers`    – ruwe tekst van één vers (debug)

De scraper gebruikt alleen **psalmboek.nl**.  Hij zoekt naar links met het
patroon `psalm={X}&psvID={Y}` in de sectie `<div class="verzen">`; die
links verwijzen exclusief naar de berijmde verzen.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import List, Set

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, APIRouter, HTTPException, Query
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("psalm_api")

app = FastAPI(title="Berijmde Psalmen 1773 API")
api = APIRouter(prefix="/api")

# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1024)
def cached_get(url: str) -> str:
    """Download pagina met eenvoudige caching."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; PsalmScraper/1.0)",
        "Accept-Language": "nl-NL,nl;q=0.9",
    }
    resp = requests.get(url, headers=headers, timeout=15)
    if resp.status_code != 200:
        raise HTTPException(resp.status_code, f"Fout bij ophalen van {url}")
    return resp.text


# ---------------------------------------------------------------------------
#  Stap 1 – bepaal hoeveel verzen een psalm heeft (berijmd)
# ---------------------------------------------------------------------------

VERSLINK_RE = re.compile(r"psalm=(?P<ps>\d+)&psvID=(?P<vers>\d+)")

@lru_cache(maxsize=150)
def get_max_berijmd_vers(psalm: int) -> int:
    """Zoek links als  psalm={psalm}&psvID={vers}  en neem hoogste vers."""
    url = f"https://psalmboek.nl/zingen.php?psalm={psalm}"
    html = cached_get(url)
    soup = BeautifulSoup(html, "html.parser")

    # Berijmde vers‑navigatie staat altijd in <div class="verzen"> … </div>
    verzen_div = soup.find("div", class_="verzen")
    if not verzen_div:
        raise HTTPException(404, f"Div.verzen niet gevonden voor Psalm {psalm}.")

    vers_nrs: Set[int] = set()
    for a in verzen_div.find_all("a", href=True):
        m = VERSLINK_RE.search(a["href"])
        if m and int(m["ps"]) == psalm:
            vers_nrs.add(int(m["vers"]))

    if not vers_nrs:
        raise HTTPException(404, f"Geen berijmde verzen gevonden voor Psalm {psalm}.")

    highest = max(vers_nrs)
    log.info("Psalm %d heeft %d verzen.", psalm, highest)
    return highest


# ---------------------------------------------------------------------------
#  Stap 2 – tekst van één vers ophalen
# ---------------------------------------------------------------------------

def extract_vers_psalmboek(psalm: int, vers: int) -> str:
    url = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID={vers}#psvs"
    html = cached_get(url)
    soup = BeautifulSoup(html, "html.parser")

    ps_div = soup.find("div", id="psvs")
    if not ps_div:
        raise HTTPException(404, "Vers-container (#psvs) niet gevonden.")

    # Eerste <h3> bevat het versnummer → verwijderen voor zuivere tekst
    first_h3 = ps_div.find("h3")
    if first_h3:
        first_h3.decompose()

    lines: List[str] = [ln.strip() for ln in ps_div.get_text("\n").split("\n") if ln.strip()]
    if not lines:
        raise HTTPException(404, "Lege vers-tekst.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
#  API‑endpoints
# ---------------------------------------------------------------------------

@api.get("/psalm/max")
def api_psalm_max(psalm: int = Query(..., ge=1, le=150)):
    """Hoogste versnummer (berijmd)."""
    return {"psalm": psalm, "max_vers": get_max_berijmd_vers(psalm)}


@api.get("/psalm")
def api_psalm(
    psalm: int = Query(..., ge=1, le=150),
    vers: int = Query(..., ge=1)
):
    max_v = get_max_berijmd_vers(psalm)
    if vers > max_v:
        raise HTTPException(400, f"Vers {vers} bestaat niet; hoogste vers is {max_v}.")
    tekst = extract_vers_psalmboek(psalm, vers)
    return {"psalm": psalm, "vers": vers, "tekst": tekst}


# ---------------------------------------------------------------------------
#  Debug-routes
# ---------------------------------------------------------------------------

@app.get("/debug/versen")
def dbg_versen(psalm: int):
    url  = f"https://psalmboek.nl/zingen.php?psalm={psalm}"
    links = VERSLINK_RE.findall(cached_get(url))
    return {"versen": [int(v) for p, v in links if int(p) == psalm]}


@app.get("/debug/vers")
def dbg_vers(psalm: int, vers: int):
    return {"tekst": extract_vers_psalmboek(psalm, vers)}


# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {"status": "Psalm‑API actief (berijmd 1773)"}

app.include_router(api)
