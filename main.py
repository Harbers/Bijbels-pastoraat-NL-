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

# Statische outbound IP-adressen (voor whitelisting indien nodig)
STATIC_OUTBOUND_IPS = ["18.156.158.53", "18.156.42.200", "52.59.103.54"]

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
    Verwerkt de HTML-content en retourneert de tekst.
    Zoekt eerst naar een container met id "psalm-tekst" of "psalmtekst".
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
    
    1. Probeer eerst expliciete markers te vinden, zoals:
       "Psalm <psalm> : <vers>", "Psalm <psalm> vers <vers>" of "Vers <vers>".
       Hierbij worden extra spaties en optionele leestekens geaccepteerd.
    2. Als een marker wordt gevonden, retourneert de functie de tekst vanaf de marker tot de volgende marker.
    3. Als geen expliciete marker wordt gevonden, wordt de tekst gesplitst op newlines en wordt de regel op positie (vers - 1) gebruikt.
    """
    patterns = [
        re.compile(rf'Psalm\s*{psalm}\s*[:\-]\s*{vers}\b', re.IGNORECASE),
        re.compile(rf'Psalm\s*{psalm}\s*vers\s*{vers}\b', re.IGNORECASE),
        re.compile(rf'\bVers\s*[:\-]?\s*{vers}\b', re.IGNORECASE)
    ]
    
    for pattern in patterns:
        m = pattern.search(text)
        if m:
            start = m.end()
            pattern_next = re.compile(r'\bVers\s*[:\-]?\s*\d+', re.IGNORECASE)
            m_next = pattern_next.search(text, pos=start)
            end = m_next.start() if m_next else len(text)
            verse_text = text[start:end].strip()
            if verse_text:
                return verse_text

    # Fallback: splits de tekst op één of meerdere newlines
    lines = re.split(r'\n+', text.strip())
    if 1 <= vers <= len(lines):
        return lines[vers - 1].strip()
    raise HTTPException(status_code=400, detail="Ongeldig versnummer of tekststructuur niet herkend.")

def get_unique_psalm_url(psalm: int, vers: int) -> str:
    """
    Probeert via psalmboek.nl het unieke URL-adres op te zoeken dat naar de gevalideerde versie
    (bijvoorbeeld met 'kernwoorden.php') leidt voor een gegeven psalm en vers.
    De basis-URL is:
         https://psalmboek.nl/zingen.php?psalm=<psalm>&psvID=<vers>#psvs
    Zoekt in de HTML naar een <a>-tag met "kernwoorden.php". Als deze gevonden wordt,
    retourneert de absolute URL; anders wordt de standaard URL gebruikt.
    """
    base_url = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID={vers}#psvs"
    html = cached_get(base_url)
    soup = BeautifulSoup(html, "html.parser")
    link = soup.find("a", href=lambda h: h and "kernwoorden.php" in h)
    if link and link.get("href"):
        unique_url = urljoin("https://psalmboek.nl/", link["href"])
        return unique_url
    return base_url

def get_psalm_text_psalmboek(psalm: int, vers: int) -> str:
    """
    Haalt de volledige psalmtekst op via psalmboek.nl.
    Eerst wordt geprobeerd het unieke URL-adres op te zoeken (met 'kernwoorden.php'),
    waarna de tekst van die URL wordt verwerkt en het gewenste vers wordt geëxtraheerd.
    """
    unique_url = get_unique_psalm_url(psalm, vers)
    html = cached_get(unique_url)
    full_text = strip_text(html)
    verse_text = extract_verse(full_text, psalm, vers)
    if not verse_text:
        raise HTTPException(status_code=404, detail="Psalmvers niet gevonden via psalmboek.nl")
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
    Endpoint voor het ophalen van een bijbeltekst via Statenvertaling (Jongbloed-editie).
    Voorbeeld: /api/bible/Genesis/1/1
    """
    text = get_bible_text(book, chapter, verse)
    return {"text": text}

@api_router.get("/psalm")
def psalm_endpoint(
    psalm: int = Query(..., description="Het psalmnummer (1 t/m 150)"),
    vers: int = Query(..., description="Het versnummer binnen de psalm"),
    source: str = Query("psalmboek", description="Bron: 'psalmboek' of 'onlinebijbel'")
):
    """
    Endpoint voor het ophalen van een psalmvers.
    
    - Bij source=psalmboek wordt de tekst opgehaald via psalmboek.nl, waarbij eerst
      het unieke URL-adres wordt opgezocht en de tekst daaruit wordt geëxtraheerd.
      
    - Bij source=onlinebijbel wordt de tekst opgehaald via:
         https://www.online-bijbel.nl/psalm/<psalm>
      en wordt daar het gevraagde vers uit gehaald.
      
    Bijvoorbeeld: /api/psalm?psalm=138&vers=2&source=psalmboek
    """
    if psalm < 1 or psalm > 150:
        raise HTTPException(status_code=400, detail="Ongeldig psalmnummer. Een psalmnummer moet tussen 1 en 150 liggen.")
    if source.lower() == "psalmboek":
        text = get_psalm_text_psalmboek(psalm, vers)
        unique_url = get_unique_psalm_url(psalm, vers)
    elif source.lower() == "onlinebijbel":
        base_url = f"https://www.online-bijbel.nl/psalm/{psalm}"
        html = cached_get(base_url)
        full_text = strip_text(html)
        text = extract_verse(full_text, psalm, vers)
        unique_url = None
    else:
        raise HTTPException(status_code=400, detail="Onbekende bronparameter.")
    return {"text": text, "unique_url": unique_url}

app.include_router(api_router, prefix="/api")
