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
    text_div = soup.find("div", {"id": "tekst"})
    if not text_div:
        raise HTTPException(status_code=404, detail="Bijbeltekst niet gevonden.")
    return text_div.get_text(strip=True)

def get_psalm_text(psalm: int, vers: int) -> str:
    # Gebruik de bron van de liturgie voor psalmen
    url = f"https://www.liturgie.nu/psalmen/{psalm}/{vers}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Fout bij ophalen van de psalmtekst.")
    soup = BeautifulSoup(response.text, "html.parser")
    # Probeer een element met id "psalmtekst" te vinden; als dit niet lukt, gebruik de gehele bodytekst.
    text_div = soup.find("div", {"id": "psalmtekst"})
    if text_div:
        text = text_div.get_text(separator="\n", strip=True)
    else:
        text = soup.get_text(separator="\n", strip=True)
    # Normaliseer de whitespace per regel, maar behoud de nieuwe lijnen
    lines = [re.sub(r'\s+', ' ', line) for line in text.splitlines()]
    normalized_text = "\n".join(lines)
    return normalized_text

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
    vers: int = Query(..., description="Het versnummer binnen de psalm"),
    hash: str = Query(None, description="Optioneel anker voor navigatie")
):
    """
    Haal een psalmvers op uit de liturgie bron.
    De tekst wordt 100% letterlijk geciteerd.
    """
    text = get_psalm_text(psalm, vers)
    return {"text": text}

@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
def serve_ai_plugin():
    bestandspad = os.path.join(os.path.dirname(__file__), ".well-known", "ai-plugin.json")
    return FileResponse(bestandspad, media_type="application/json")

@app.get("/openapi.yaml", include_in_schema=False)
def serve_openapi():
    bestandspad = os.path.join(os.path.dirname(__file__), "openapi.yaml")
    return FileResponse(bestandspad, media_type="text/yaml")
