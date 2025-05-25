from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import requests
from bs4 import BeautifulSoup

app = FastAPI(title="Berijmde Psalmen API", version="1.0")

def scrape_psalmboek(psalm, vers):
    url = f"https://psalmboek.nl/berijmd/{psalm}/{vers}"
    resp = requests.get(url)
    if resp.status_code != 200:
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    verse_div = soup.find("div", {"class": "psalmtekst"})
    if not verse_div:
        return None
    paragraphs = verse_div.find_all("p")
    # Let op: meestal index = 0 voor vers 1, 1 voor vers 2, etc.
    if len(paragraphs) >= vers:
        return paragraphs[vers-1].get_text(strip=True)
    return None

def scrape_liturgie(psalm, vers):
    url = f"https://www.liturgie.nu/psalmen/{psalm}"
    resp = requests.get(url)
    if resp.status_code != 200:
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    # Voorbeeld-structuur, pas aan na inspectie van de site!
    verses = soup.find_all("div", class_="vers")
    if len(verses) >= vers:
        return verses[vers-1].get_text(strip=True)
    return None

def scrape_bijbelbox(psalm, vers):
    url = f"https://bijbelbox.nl/psalmen/{psalm}/berijmd"
    resp = requests.get(url)
    if resp.status_code != 200:
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    verses = soup.find_all("li", class_="psalm-vers")
    if len(verses) >= vers:
        return verses[vers-1].get_text(strip=True)
    return None

@app.get("/psalm")
def get_berijmd_psalmvers(psalm: int = Query(..., ge=1, le=150), vers: int = Query(..., ge=1)):
    # Probeer psalmboek.nl
    tekst = scrape_psalmboek(psalm, vers)
    if tekst:
        return {"bron": "psalmboek.nl", "tekst": tekst}
    # Probeer liturgie.nu
    tekst = scrape_liturgie(psalm, vers)
    if tekst:
        return {"bron": "liturgie.nu", "tekst": tekst}
    # Probeer bijbelbox.nl
    tekst = scrape_bijbelbox(psalm, vers)
    if tekst:
        return {"bron": "bijbelbox.nl", "tekst": tekst}
    return JSONResponse(status_code=404, content={"detail": "Vers niet gevonden in de online bronnen."})

@app.get("/status")
def status():
    return {"status": "ok"}
