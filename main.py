from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup
import re

app = FastAPI(
    title="Bijbelse Psalmen API",
    version="1.0",
    openapi_url="/openapi.yaml"
)

class PsalmVers(BaseModel):
    psalm: int
    vers: int
    text: str
    bron: str

class Error(BaseModel):
    detail: str

async def fetch_vers(ps: int, vs: int) -> str | None:
    url = f"https://psalmboek.nl/zingen.php?psalm={ps}&psvID={vs}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    # p binnen div.content
    container = soup.select_one("div.content") or soup
    p = container.find("p")
    if not p:
        return None
    # bewaar linebreaks
    lines = [line.strip() for line in p.get_text(separator="\n").split("\n") if line.strip()]
    return "\n".join(lines)

async def fetch_max(ps: int) -> int | None:
    url = f"https://psalmboek.nl/zingen.php?psalm={ps}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    if r.status_code != 200:
        return None
    # vind alle psvID=xx
    matches = re.findall(r"psvID=(\d+)", r.text)
    vers_nums = {int(m) for m in matches}
    return max(vers_nums) if vers_nums else None

@app.get(
    "/api/psalm",
    response_model=PsalmVers,
    responses={404: {"model": Error}},
    summary="Haal één berijmd psalmvers (1773)"
)
async def get_psalm_vers(
    psalm: int = Query(..., ge=1, le=150),
    vers:  int = Query(..., ge=1)
):
    text = await fetch_vers(psalm, vers)
    if not text:
        raise HTTPException(status_code=404, detail=f"Vers {vers} van Psalm {psalm} kon niet worden opgehaald.")
    return PsalmVers(psalm=psalm, vers=vers, text=text, bron="psalmboek.nl/zingen.php")

@app.get(
    "/api/psalm/max",
    response_model=int,
    responses={404: {"model": Error}},
    summary="Geef maximaal versnummer in 1773-berijming"
)
async def get_psalm_max(
    psalm: int = Query(..., ge=1, le=150)
):
    maxv = await fetch_max(psalm)
    if not maxv:
        raise HTTPException(status_code=404, detail=f"Geen verzen gevonden voor Psalm {psalm}.")
    return maxv
