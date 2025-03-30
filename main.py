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
    Verwerkt de HTML-content en retourneert de tekst.
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
    
    1. Eerst wordt gezocht naar een marker met het patroon "Vers <nummer>" of "Psalm <psalm>:<vers>".
    2. Als een marker gevonden wordt, wordt de tekst tussen deze marker en de volgende marker gebruikt.
    3. Anders wordt de tekst gesplitst op nieuwe regels en wordt de regel op positie (vers-1) gebruikt.
    
    Deze aanpak is universeel toepasbaar voor alle psalmen, mits de bron een consistente structuur hanteert.
    """
    # Zoek naar een marker: "Psalm <psalm>:<vers>" of "Psalm <psalm> vers <vers>"
    pattern_colon = re.compile(rf'Psalm\s*{psalm}\s*:\s*{vers}\b', re.IGNORECASE)
    pattern_vers = re.compile(rf'Psalm\s*{psalm}\s*vers\s*{vers}\b', re.IGNORECASE)
    m = pattern_colon.search(text) or pattern_vers.search(text)
    if m:
        start = m.end()
        pattern_next = re.compile(rf'Psalm\s*{psalm}\s*(?:vers|:)\s*\d+', re.IGNORECASE)
        m_next = pattern_next.search(text, pos=start)
        end = m_next.start() if m_next else len(text)
        verse_text = text[start:end].strip()
        if verse_text:
            return verse_text

    # Fallback: splits de tekst op nieuwe regels en gebruik de regel op positie (vers - 1)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if 1 <= vers <= len(lines):
        return lines[vers - 1]
    raise HTTPException(status_code=400, detail="Ongeldig versnummer of tekststructuur niet herkend.")

def get_unique_psalm_url(psalm: int, vers: int) -> str:
    """
    Probeert via psalmboek.nl het unieke URL-adres op te zoeken dat naar de gevalideerde
    versie (bijvoorbeeld met 'kernwoorden.php') leidt voor een gegeven psalm en vers.
    De basis-URL is:
         https://psalmboek.nl/zingen.php?psalm=<psalm>&psvID=<vers>#psvs
    Zoeken we in de HTML naar een <a>-tag met een href waarin "kernwoorden.php" voorkomt.
    Als deze link wordt gevonden, wordt de absolute URL teruggegeven.
    """
    base_url = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID={vers}#psvs"
    html = cached_get(base_url)
    soup = BeautifulSoup(html, "html.parser")
    link = soup.find("a", href=lambda h: h and "kernwoorden.php" in h)
    if link and link.get("href"):
        unique_url = urljoin("https://psalmboek.nl/", link["href"])
        return unique_url
    # Als er geen unieke URL wordt gevonden, geef dan de standaard URL terug
    return base_url

def get_psalm_text_psalmboek(psalm: int, vers: int) -> str:
    """
    Haalt de volledige psalmtekst op via psalmboek.nl.
    Eerst wordt geprobeerd om het unieke URL-adres op te zoeken dat de gevalideerde tekst bevat.
    Vervolgens wordt de tekst van die URL verwerkt en wordt het gewenste vers geëxtraheerd.
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
    Endpoint voor het ophalen van een bijbeltekst uit de externe bron (Statenvertaling, Jongbloed-editie).
    Bijvoorbeeld: /api/bible/Genesis/1/1
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
    
    - Bij source=psalmboek wordt de tekst opgehaald via psalmboek.nl. Hierbij wordt eerst
      het unieke URL-adres opgezocht en vervolgens de tekst uit dat adres geëxtraheerd.
      
    - Bij source=onlinebijbel wordt de tekst opgehaald via:
         https://www.online-bijbel.nl/psalm/<psalm>
      en wordt daar het gevraagde vers uit gehaald.
      
    Bijvoorbeeld: /api/psalm?psalm=51&vers=3&source=psalmboek
    """
    if psalm < 1 or psalm > 150:
        raise HTTPException(status_code=400, detail="Ongeldig psalmnummer. Een psalmnummer moet tussen 1 en 150 liggen.")
    if source.lower() == "psalmboek":
        text = get_psalm_text_psalmboek(psalm, vers)
    elif source.lower() == "onlinebijbel":
        # Gebruik een alternatieve bron als dat gewenst is
        base_url = f"https://www.online-bijbel.nl/psalm/{psalm}"
        html = cached_get(base_url)
        full_text = strip_text(html)
        text = extract_verse(full_text, psalm, vers)
    else:
        raise HTTPException(status_code=400, detail="Onbekende bronparameter.")
    return {"text": text, "unique_url": get_unique_psalm_url(psalm, vers) if source.lower() == "psalmboek" else None}

# Voeg de API-router toe met prefix "/api"
app.include_router(api_router, prefix="/api")
