from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
import os
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import quote

app = FastAPI()

@app.get("/")
def root():
    return {"status": "Backend GPT is actief"}

def get_bible_text(book: str, chapter: int, verse: int) -> str:
    # Gebruik de bron van de Statenvertaling (Jongbloed-editie)
    url = f"https://www.statenvertaling.net/bijbel/{quote(book)}/{chapter}/{verse}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Fout bij ophalen van de bijbeltekst.")
    soup = BeautifulSoup(response.text, "html.parser")
    # Pas dit element aan indien nodig, afhankelijk van de HTML-structuur van de bron
    text_div = soup.find("div", {"id": "tekst"})
    if not text_div:
        raise HTTPException(status_code=404, detail="Bijbeltekst niet gevonden.")
    # Zorg dat de tekst 100% letterlijk wordt geciteerd
    return text_div.get_text(strip=True)

def get_psalm_text(psalm: int, psvID: int) -> str:
    # Gebruik de bron van de 1773 berijming voor psalmen en gezangen
    url = f"https://psalmboek.nl/psalmen.php?psalm={psalm}&psvID={psvID}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Fout bij ophalen van de psalmtekst.")
    soup = BeautifulSoup(response.text, "html.parser")
    # Aangenomen wordt dat de tekst zich bevindt in een element met id "psvs"
    div = soup.find("div", {"id": "psvs"})
    if not div:
        raise HTTPException(status_code=404, detail="Psalmtekst niet gevonden.")
    text = div.get_text(separator="\n", strip=True)
    # Normaliseer de whitespace zonder de originele structuur te verliezen
    text = re.sub(r'\s+', ' ', text)
    return text

@app.get("/bible/{book}/{chapter}/{verse}")
def bible_endpoint(book: str, chapter: int, verse: int):
    """
    Haal een bijbeltekst op uit de Statenvertaling (Jongbloed-editie).
    De tekst wordt 100% letterlijk geciteerd.
    """
    text = get_bible_text(book, chapter, verse)
    return {"text": text}

@app.get("/psalm")
def psalm_endpoint(
    psalm: int = Query(..., description="Het psalmnummer"),
    psvID: int = Query(..., description="Het versnummer binnen de psalm"),
    hash: str = Query(None, description="Optioneel anker voor navigatie")
):
    """
    Haal een psalmvers op uit de berijming van 1773.
    De tekst wordt 100% letterlijk geciteerd.
    """
    text = get_psalm_text(psalm, psvID)
    return {"text": text}
@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
def serve_ai_plugin():
    bestandspad = os.path.join(os.path.dirname(__file__), ".well-known", "ai-plugin.json")
    return FileResponse(bestandspad, media_type="application/json")

@app.get("/openapi.yaml", include_in_schema=False)
def serve_openapi():
    bestandspad = os.path.join(os.path.dirname(__file__), "openapi.yaml")
    return FileResponse(bestandspad, media_type="application/yaml")
