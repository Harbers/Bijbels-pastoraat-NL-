#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi import FastAPI, APIRouter, HTTPException, Query
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from functools import lru_cache
import re

app = FastAPI()

# Root-route voor de hoofd-URL
@app.get("/")
def root():
    return {"status": "Bijbels Pastoraat API draait correct"}

# Maak een APIRouter met prefix "/api"
api_router = APIRouter()

# Eenvoudige cache voor opgevraagde content
@lru_cache(maxsize=1024)
def cached_get(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.text
    else:
        raise HTTPException(status_code=response.status_code,
                            detail=f"Fout bij ophalen van URL: {url}")

def strip_text(html_content: str) -> str:
    """
    Verwerk de HTML-content en retourneer de tekst.
    Probeert eerst een container met id "psalm-tekst" te vinden.
    Als dat niet lukt, wordt de volledige pagina-tekst gebruikt.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    container = soup.find("div", {"id": "psalm-tekst"})
    if container:
        return container.get_text(separator="\n", strip=True)
    return soup.get_text(separator="\n", strip=True)

def extract_verse(text: str, psalm: int, vers: int) -> str:
    """
    Probeert de gewenste psalmregel te extraheren.
    
    1. Eerst zoeken we naar een header waarin "Psalm <psalm> vers <vers>" of "Psalm <psalm>:<vers>" voorkomt.
    2. Als dat lukt, nemen we de tekst vanaf de header tot de volgende header als het vers.
    3. Als geen duidelijke marker gevonden wordt, splitsen we de tekst op nieuwe regels en nemen we de regel die overeenkomt met het versnummer.
    """
    # Zoek naar een header met het patroon "Psalm <psalm> vers <vers>" of "Psalm <psalm>:<vers>"
    pattern = re.compile(rf'Psalm\s*{psalm}\s*(?:vers|:)\s*{vers}', re.IGNORECASE)
    m = pattern.search(text)
    if m:
        start = m.end()
        # Zoek naar de volgende header voor hetzelfde psalm (bijv. "Psalm <psalm> vers <n>")
        pattern_next = re.compile(rf'Psalm\s*{psalm}\s*(?:vers|:)\s*\d+', re.IGNORECASE)
        m_next = pattern_next.search(text, pos=start)
        end = m_next.start() if m_next else len(text)
        verse_text = text[start:end].strip()
        if verse_text:
            return verse_text

    # Fallback: splits de tekst op nieuwe regels en neem de regel op positie (vers-1)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if 1 <= vers <= len(lines):
        return lines[vers - 1]
    raise HTTPException(status_code=400, detail="Ongeldig versnummer of tekststructuur niet herkend.")

def get_psalm_text_liturgie(psalm: int, vers: int) -> str:
    """
    Haal de volledige psalmtekst op via liturgie.nu en extraheer het gevraagde vers.
    We gaan ervan uit dat de psalm beschikbaar is op:
         https://www.liturgie.nu/psalmen/<psalm>
    en dat de tekst in een container met id "psalm-tekst" staat.
    """
    base_url = f"https://www.liturgie.nu/psalmen/{psalm}"
    html = cached_get(base_url)
    full_text = strip_text(html)
    verse_text = extract_verse(full_text, psalm, vers)
    if not verse_text:
        raise HTTPException(status_code=404, detail="Psalmvers niet gevonden.")
    return verse_text

def get_bible_text(book: str, chapter: int, verse: int) -> str:
    """
    Haal de bijbeltekst op via een externe bron (Statenvertaling, Jongbloed-editie).
    """
    url = f"https://www.statenvertaling.net/bijbel/{quote(book)}/{chapter}/{verse}"
    html = cached_get(url)
    text = strip_text(html)
    if not text:
        raise HTTPException(status_code=404, detail="Bijbeltekst niet gevonden.")
    return text

@api_router.get("/bible/{book}/{chapter}/{verse}")
def bible_endpoint(book: str, chapter: int, verse: int):
    """
    Endpoint voor het ophalen van een bijbeltekst uit de externe bron (Statenvertaling, Jongbloed-editie).
    Voorbeeld: /api/bible/Genesis/1/1
    """
    text = get_bible_text(book, chapter, verse)
    return {"text": text}

@api_router.get("/psalm")
def psalm_endpoint(
    psalm: int = Query(..., description="Het psalmnummer (1 t/m 150)"),
    vers: int = Query(..., description="Het versnummer binnen de psalm"),
    hash: str = Query(None, description="Optioneel anker voor navigatie")
):
    """
    Endpoint voor het ophalen van een psalmvers via liturgie.nu.
    De volledige psalm wordt opgehaald via:
         https://www.liturgie.nu/psalmen/<psalm>
    De tekst wordt vervolgens gesplitst op basis van herkenningspunten of nieuwe regels,
    zodat het gevraagde vers (op basis van het versnummer) kan worden teruggegeven.
    Voorbeeld: /api/psalm?psalm=128&vers=1
    """
    if psalm < 1 or psalm > 150:
        raise HTTPException(status_code=400, detail="Ongeldig psalmnummer. Een psalmnummer moet tussen 1 en 150 liggen.")
    text = get_psalm_text_liturgie(psalm, vers)
    return {"text": text}

# Voeg de API-router toe met prefix /api
app.include_router(api_router, prefix="/api")
