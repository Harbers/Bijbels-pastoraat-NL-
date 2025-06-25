#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bijbelse Psalmen API – FastAPI backend (versie 1.0)"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup

app = FastAPI(title="Bijbelse Psalmen API", version="1.0")

# ----------------------------- Modellen -----------------------------
class PsalmVers(BaseModel):
    psalm: int
    vers: int
    text: str
    bron: str

class Error(BaseModel):
    detail: str

# ------------------------- Statische bestanden ----------------------
@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
async def serve_ai_plugin():
    return FileResponse("ai-plugin.json", media_type="application/json")

@app.get("/openapi.yaml", include_in_schema=False)
async def serve_openapi():
    return FileResponse("openapi.yaml", media_type="text/yaml")

# ---------------------------- Scrapers ------------------------------
async def fetch_from_zingen(ps: int, vs: int):
    url = f"https://psalmboek.nl/zingen.php?psalm={ps}&psvID={vs}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    p = soup.select_one("div.content p") or soup.find("p")
    if not p:
        return None
    return p.get_text(separator="\n", strip=True), "psalmboek.nl/zingen.php"

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
    return stanza.get_text(separator="\n", strip=True), url

async def fetch_from_refo(ps: int, vs: int):
    url = f"https://content.reformatorischeomroep.nl/psalmen/berijming-1773/{ps}/{vs}.txt"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    text = r.text.strip()
    return (text, url) if text else None

SCRAPERS = [fetch_from_zingen, fetch_from_old, fetch_from_refo]

# ----------------------------- API Routes ---------------------------
@app.get("/api/psalm", response_model=PsalmVers, responses={404: {"model": Error}})
async def get_psalm_vers(psalm: int = Query(..., ge=1, le=150), vers: int = Query(..., ge=1)):
    """Haal één berijmd psalmvers (1773‑berijming) op uit drie bronnen."""
    for scraper in SCRAPERS:
        result = await scraper(psalm, vers)
        if result:
            text, bron = result
            return PsalmVers(psalm=psalm, vers=vers, text=text, bron=bron)
    raise HTTPException(404, detail=f"Vers {vers} van Psalm {psalm} kon niet worden opgehaald.")

@app.get("/api/psalm/max", response_model=int, responses={404: {"model": Error}})
async def get_psalm_max(psalm: int = Query(..., ge=1, le=150)):
    """Bepaal het hoogste versnummer in de 1773‑berijming voor een psalm."""
    url = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID=0"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        raise HTTPException(404, detail=f"Psalm {psalm} niet gevonden.")
    soup = BeautifulSoup(r.text, "html.parser")
    opts = soup.select("select[name=psvID] option")
    waarden = [o["value"] for o in opts if o.get("value", "").isdigit()]
    if not waarden:
        raise HTTPException(404, detail=f"Geen verzen gevonden voor Psalm {psalm}.")
    return max(int(v) for v in waarden)

# ------------------------- Root‑endpoint ----------------------------
@app.get("/")
def root():
    return {"status": "Bijbelse Psalmen API draait", "version": app.version}

# ------------------ Lokale run (ontwikkel‑stand) --------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
