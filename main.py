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

def get_psalm_text_fallback(psalm: int, vers: int) -> str:
    """
    Haal de gehele psalm op via de fallback-bron en extraheer het gewenste vers.
    """
    url = f"https://www.bijbelbox.nl/psalmen/psalm-{psalm}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, 
                            detail="Fout bij ophalen van de psalmtekst (fallback bron).")
    soup = BeautifulSoup(response.text, "html.parser")
    # Probeer een element met id "psalmtekst" te vinden; zo niet, gebruik de gehele bodytekst.
    text_div = soup.find("div", {"id": "psalmtekst"})
    if text_div:
        text_full = text_div.get_text(separator="\n", strip=True)
    else:
        text_full = soup.get_text(separator="\n", strip=True)
    # Splits de volledige tekst in regels (aangenomen dat elke regel een vers vertegenwoordigt)
    verses = [line.strip() for line in text_full.splitlines() if line.strip() != ""]
    if vers < 1 or vers > len(verses):
        raise HTTPException(status_code=400, detail=f"Versnummer {vers} is ongeldig. Deze psalm heeft {len(verses)} verzen.")
    return verses[vers-1]

def get_psalm_text(psalm: int, vers: int) -> str:
    """
    Probeer eerst de psalmtekst op te halen via liturgie.nu.
    Als dit mislukt, wordt de fallback-bron (bijbelbox.nl) gebruikt.
    """
    url_primary = f"https://www.liturgie.nu/psalmen/{psalm}/{vers}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url_primary, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        text_div = soup.find("div", {"id": "psalmtekst"})
        if text_div:
            text = text_div.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)
        lines = [re.sub(r'\s+', ' ', line) for line in text.splitlines()]
        normalized_text = "\n".join(lines)
        # Indien de verkregen tekst leeg blijkt of geen zinvolle inhoud heeft, activeren we de fallback
        if not normalized_text.strip():
            return get_psalm_text_fallback(psalm, vers)
        return normalized_text
    else:
        # Als de primaire bron niet reageert, wordt de fallback gebruikt.
        return get_psalm_text_fallback(psalm, vers)

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
    psalm: int = Query(..., description="Het psalmnummer (1 t/m 150)"),
    vers: int = Query(..., description="Het versnummer binnen de psalm"),
    hash: str = Query(None, description="Optioneel anker voor navigatie")
):
    """
    Haal een psalmvers op.
    Voor de berijmde psalmen geldt dat bijvoorbeeld Psalm 119 slechts 88 verzen heeft.
    De tekst wordt 100% letterlijk geciteerd.
    Indien de primaire bron (liturgie.nu) faalt, wordt de fallback-bron (bijbelbox.nl) gebruikt.
    """
    # Validatie van het psalmnummer
    if psalm < 1 or psalm > 150:
        raise HTTPException(status_code=400, detail="Ongeldig psalmnummer. Een psalmnummer moet tussen 1 en 150 liggen.")
    # Specifieke validatie voor Psalm 119
    if psalm == 119:
        if vers < 1 or vers > 88:
            raise HTTPException(status_code=400, detail="Voor Psalm 119 moet het versnummer tussen 1 en 88 liggen.")
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
