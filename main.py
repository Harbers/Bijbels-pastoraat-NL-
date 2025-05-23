"""FastAPI-backend voor het ophalen van berijmde psalmteksten (1773).

Belangrijkste punten
--------------------
*   Scraping uitsluitend van **psalmboek.nl** (berijming 1773).
*   Strikte validatie van het aantal verzen per psalm via de links in
    `<div class="verzen">`.
*   Geen automatische fallback naar onberijmde bronnen; een alternatieve
    bron moet expliciet worden opgegeven.
*   Caching – om server en remote‑site te ontzien – via functools.lru_cache.
*   Extra *debug‑routes* om HTML en gedetecteerde versnummers te bekijken.
"""
from __future__ import annotations

import logging
from functools import lru_cache

import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, FastAPI, HTTPException, Query

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("psalm_api")

app = FastAPI()
api_router = APIRouter(prefix="/api")

# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1024)
def cached_get(url: str) -> str:  # pragma: no cover
    """Download pagina met eenvoudige caching en basis‑headers."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; PsalmScraper/1.0)",
        "Accept-Language": "nl-NL,nl;q=0.9",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
    except requests.RequestException as exc:  # netwerkstoring e.d.
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"Fout bij ophalen van URL: {url}",
        )

    return resp.text


# ---------------------------------------------------------------------------
#  Kern‑functionaliteit
# ---------------------------------------------------------------------------

@lru_cache(maxsize=150)
def get_max_berijmd_vers(psalm: int) -> int:
    """Bepaal het aantal verzen in *berijmde* Psalm 1773.

    We lezen *uitsluitend* de links binnen `<div class="verzen">` die
    zowel `psalm={psalm}` als `psvID=` bevatten. Dat zijn exact de
    vers‑navigatielinks voor de gevraagde psalm.
    """
    url = f"https://psalmboek.nl/zingen.php?psalm={psalm}"
    soup = BeautifulSoup(cached_get(url), "html.parser")

    links = soup.select(
        f"div.verzen a[href*='psalm={psalm}'][href*='psvID=']"
    )
    vers_nummers: set[int] = {
        int(a.get_text(strip=True))
        for a in links
        if a.get_text(strip=True).isdigit()
    }

    if not vers_nummers:
        raise HTTPException(
            status_code=404,
            detail=f"Geen berijmde verzen gevonden voor Psalm {psalm}.",
        )

    hoogste = max(vers_nummers)
    logger.debug("Psalm %d heeft %d verzen", psalm, hoogste)
    return hoogste


def validate_berijmd_vers(psalm: int, vers: int) -> None:
    """Valideer of *vers* binnen bereik ligt voor deze psalm."""
    max_vers = get_max_berijmd_vers(psalm)
    if not (1 <= vers <= max_vers):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Psalm {psalm}:{vers} bestaat niet in de berijming 1773. "
                f"Toegestane range 1–{max_vers}."
            ),
        )


def extract_vers_psalmboek(psalm: int, vers: int) -> str:
    """Haal de berijmde tekst (couplet) op uit psalmboek.nl."""
    url = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID={vers}#psvs"
    soup = BeautifulSoup(cached_get(url), "html.parser")
    tekst_bloc = soup.find("div", id="psvs")
    if not tekst_bloc:
        raise HTTPException(
            status_code=404,
            detail="Tekstblok met vers niet gevonden op psalmboek.nl",
        )
    return tekst_bloc.get_text("\n", strip=True)


# Optioneel: onberijmde fallback – alleen gebruiken als gebruiker erom vraagt

def extract_vers_onlinebijbel(psalm: int, vers: int) -> str:  # pragma: no cover
    url = f"https://www.online-bijbel.nl/psalm/{psalm}"
    soup = BeautifulSoup(cached_get(url), "html.parser")
    regels = [r.strip() for r in soup.get_text("\n").split("\n") if r.strip()]
    if vers > len(regels):
        raise HTTPException(
            status_code=404, detail="Vers niet gevonden bij online-bijbel.nl"
        )
    return regels[vers - 1]


# ---------------------------------------------------------------------------
#  API‑routes
# ---------------------------------------------------------------------------

@api_router.get("/psalm")
def psalm_endpoint(
    psalm: int = Query(..., ge=1, le=150, description="Psalmnummer"),
    vers: int = Query(..., ge=1, description="Versnummer in berijming 1773"),
    bron: str = Query(
        "psalmboek",
        regex="^(psalmboek|onlinebijbel)$",
        description="psalmboek = berijmd 1773, onlinebijbel = onberijmd",
    ),
):
    """Geef één vers terug in JSON‑vorm."""
    validate_berijmd_vers(psalm, vers)

    if bron == "psalmboek":
        tekst = extract_vers_psalmboek(psalm, vers)
    else:  # expliciet om onberijmde bron gevraagd
        tekst = extract_vers_onlinebijbel(psalm, vers)

    return {"psalm": psalm, "vers": vers, "tekst": tekst}


@api_router.get("/psalm/max")
def psalm_max_endpoint(psalm: int = Query(..., ge=1, le=150)):
    """Retourneer het **aantal** berijmde verzen (coupletten) voor deze psalm."""
    return {"psalm": psalm, "max_vers": get_max_berijmd_vers(psalm)}


# ---------------------------------------------------------------------------
#  Debug‑routes (handig tijdens ontwikkeling)
# ---------------------------------------------------------------------------

@app.get("/debug/versen")
def debug_versen(psalm: int):  # pragma: no cover – niet voor productie
    soup = BeautifulSoup(cached_get(f"https://psalmboek.nl/zingen.php?psalm={psalm}"), "html.parser")
    links = soup.select(
        f"div.verzen a[href*='psalm={psalm}'][href*='psvID=']"
    )
    return {
        "versen": [a.get_text(strip=True) for a in links if a.get_text(strip=True).isdigit()]
    }


@app.get("/debug/html")
def debug_html(psalm: int):  # pragma: no cover – niet voor productie
    html = cached_get(f"https://psalmboek.nl/zingen.php?psalm={psalm}")
    return {"html": html[:5000]}


# ---------------------------------------------------------------------------
#  Basisroute en router‑registratie
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {"status": "Psalm API actief"}


app.include_router(api_router)
