#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi import FastAPI, APIRouter, HTTPException, Query
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin
from functools import lru_cache
import re

app = FastAPI()

# Root-route voor statuscontrole
@app.get("/")
def root():
    return {"status": "Bijbels Pastoraat API draait correct"}

# Maak een API-router met prefix "/api"
api_router = APIRouter()

# Eenvoudige cache voor HTTP-aanvragen
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
    Probeert eerst een container met id "psalm-tekst" of "psalmtekst" te vinden.
    Als deze niet wordt gevonden, retourneert hij de volledige pagina-tekst.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    container = soup.find("div", {"id": "psalm-tekst"}) or soup.find("div", {"id": "psalmtekst"})
    if container:
        return container.get_text(separator="\n", strip=True)
    return soup.get_text(separator="\n", strip=True)

def extract_verse(text: str, psalm: int, vers: int) -> str:
    """
    Extraheert het gevraagde vers uit de volledige psalmtekst.
    
    1. We proberen eerst expliciet te zoeken naar een marker waarin de header "Psalm <psalm>" 
       gevolgd door een aanduiding van het vers (bijvoorbeeld "Psalm 119:3" of "Psalm 119 vers 3") voorkomt.
    2. Als een dergelijke marker wordt gevonden, wordt de tekst tussen deze marker en de volgende marker (of het einde van de tekst) als het vers beschouwd.
    3. Als geen expliciete marker wordt gevonden, wordt de tekst opgedeeld in regels (gesplitst op nieuwe regels)
       en wordt de regel op positie (vers - 1) als fallback gebruikt.
       
    Deze aanpak is universeel toepasbaar, ook voor psalmen waarvan de verzen anders zijn ingedeeld (zoals de berijmde Psalm 119).
    """
    # Zoek naar een marker voor het gevraagde vers
    # We maken gebruik van twee patronen: een voor "Psalm <psalm>:<vers>" en een voor "Psalm <psalm> vers <vers>"
    pattern_colon = re.compile(rf'Psalm\s*{psalm}\s*:\s*{vers}\b', re.IGNORECASE)
    pattern_vers = re.compile(rf'Psalm\s*{psalm}\s*vers\s*{vers}\b', re.IGNORECASE)
    
    m = pattern_colon.search(text) or pattern_vers.search(text)
    if m:
        start = m.end()
        # Zoek naar de volgende marker voor een vers (wellicht voor "Vers <nummer>")
        pattern_next = re.compile(r'Vers\s*(?:[:.]?\s*\d+)', re.IGNORECASE)
        m_next = pattern_next.search(text, pos=start)
        end = m_next.start() if m_next else len(text)
        verse_text = text[start:end].strip()
        if verse_text:
            return verse_text

    # Fallback: splits de tekst op basis van nieuwe regels
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    # Debug: log de hoeveelheid regels (optioneel, voor debugging)
    # print(f"Extracted {len(lines)} lines from psalm {psalm}")
    if 1 <= vers <= len(lines):
        return lines[vers - 1]
    raise HTTPException(status_code=400, detail="Ongeldig versnummer of tekststructuur niet herkend.")

def get_psalm_text_onlinebijbel(psalm: int, vers: int) -> str:
    """
    Haalt de volledige psalmtekst op via Online-Bijbel.nl.
    De tekst wordt opgehaald via:
         https://www.online-bijbel.nl/psalm/<psalm>
    Vervolgens wordt de tekst verwerkt met strip_text() en het gevraagde vers wordt geëxtraheerd met extract_verse().
    Deze methode is universeel toepasbaar voor alle psalmen.
    """
    base_url = f"https://www.online-bijbel.nl/psalm/{psalm}"
    html = cached_get(base_url)
    full_text = strip_text(html)
    verse_text = extract_verse(full_text, psalm, vers)
    if not verse_text:
        raise HTTPException(status_code=404, detail="Psalmvers niet gevonden op Online-Bijbel.nl")
    return verse_text

def get_bible_text(book: str, chapter: int, verse: int) -> str:
    """
    Haalt de bijbeltekst op via een externe bron (Statenvertaling, Jongbloed-editie).
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
    Endpoint voor het ophalen van een psalmvers via Online-Bijbel.nl.
    De volledige psalm wordt opgehaald via:
         https://www.online-bijbel.nl/psalm/<psalm>
    Vervolgens wordt de tekst verwerkt en het gevraagde vers (op basis van herkenningspunten of regel-splitsing) geëxtraheerd.
    Voorbeeld: /api/psalm?psalm=119&vers=3
    """
    if psalm < 1 or psalm > 150:
        raise HTTPException(status_code=400, detail="Ongeldig psalmnummer. Een psalmnummer moet tussen 1 en 150 liggen.")
    text = get_psalm_text_onlinebijbel(psalm, vers)
    return {"text": text}

# Voeg de API-router toe met prefix "/api"
app.include_router(api_router, prefix="/api")
