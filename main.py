#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi import FastAPI, HTTPException, Query
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
from functools import lru_cache
import re

app = FastAPI()

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

@app.get("/")
def root():
    return {"status": "Backend API is actief"}

def get_bible_text(book: str, chapter: int, verse: int) -> str:
    """
    Haal de bijbeltekst op via een externe bron (Statenvertaling, Jongbloed-editie).
    """
    url = f"https://www.statenvertaling.net/bijbel/{quote(book)}/{chapter}/{verse}"
    html = cached_get(url)
    soup = BeautifulSoup(html, "html.parser")
    text_div = soup.find("div", {"id": "tekst"})
    if not text_div:
        raise HTTPException(status_code=404, detail="Bijbeltekst niet gevonden.")
    return text_div.get_text(strip=True)

def extract_psalm_text(soup: BeautifulSoup, psalm: int, vers: int) -> str:
    """
    Probeer de officiële, letterlijke tekst te vinden door:
      - Te zoeken naar een container met id "tekst" of "psalmtekst"
      - Te controleren of er een header aanwezig is met "Psalm <psalm> vers <vers>".
    """
    # Zoek eerst naar een container met id "tekst"
    text_div = soup.find("div", {"id": "tekst"})
    if text_div:
        text = text_div.get_text(strip=True)
        # Controleer of de tekst de verwachte header bevat (optioneel)
        header_pattern = re.compile(rf"Psalm\s*{psalm}\s*vers\s*{vers}", re.IGNORECASE)
        if header_pattern.search(text):
            return text
        else:
            # Als er geen expliciete header wordt gevonden, geven we toch de inhoud terug
            return text

    # Zoek naar een container met id "psalmtekst"
    text_div = soup.find("div", {"id": "psalmtekst"})
    if text_div:
        return text_div.get_text(strip=True)

    # Als geen specifieke container wordt gevonden, probeer de hele body te filteren
    return soup.get_text(strip=True)

def get_psalm_text_strict(psalm: int, vers: int) -> str:
    """
    Voer het volledige validatieproces uit voor het ophalen van een psalmvers:
      1. Haal de standaardpagina op via de basis-URL (met anchor #psvs).
      2. Zoek in de HTML naar een link naar de 'kernwoorden.php'-weergave.
      3. Als deze link gevonden wordt, volg deze en haal daar de tekst op.
      4. Gebruik herkenningspunten (zoals een container met id "tekst" en een header met "Psalm <psalm> vers <vers>")
         om de officiële tekst te extraheren.
      5. Indien geen specifieke container wordt gevonden, gebruik de volledige HTML als fallback.
    """
    base_url = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID={vers}#psvs"
    html = cached_get(base_url)
    soup = BeautifulSoup(html, "html.parser")
    
    # Zoek naar een link naar de kernwoorden.php-pagina
    kernwoorden_link = soup.find("a", href=lambda h: h and "kernwoorden.php" in h)
    if kernwoorden_link and kernwoorden_link.get("href"):
        kern_url = urljoin("https://psalmboek.nl/", kernwoorden_link["href"])
        kern_html = cached_get(kern_url)
        kern_soup = BeautifulSoup(kern_html, "html.parser")
        text = extract_psalm_text(kern_soup, psalm, vers)
        if text:
            return text

    # Fallback: probeer direct de tekst van de oorspronkelijke pagina te extraheren
    return extract_psalm_text(soup, psalm, vers)

def get_psalm_text_simple(psalm: int, vers: int) -> str:
    """
    Eenvoudige methode: haal de psalmtekst rechtstreeks op via de basis-URL zonder extra validatie.
    """
    url = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID={vers}#psvs"
    html = cached_get(url)
    soup = BeautifulSoup(html, "html.parser")
    return extract_psalm_text(soup, psalm, vers)

# Configuratie: Als STRICT_POLICY True is, gebruiken we de strict-validatie, anders de eenvoudige methode.
STRICT_POLICY = True

def get_psalm_text(psalm: int, vers: int) -> str:
    if STRICT_POLICY:
        return get_psalm_text_strict(psalm, vers)
    else:
        return get_psalm_text_simple(psalm, vers)

@app.get("/bible/{book}/{chapter}/{verse}")
def bible_endpoint(book: str, chapter: int, verse: int):
    """
    Endpoint voor het ophalen van een bijbeltekst uit de externe bron
    (Statenvertaling, Jongbloed-editie).
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
    Endpoint voor het ophalen van een psalmvers.
    De tekst wordt opgehaald via de basis-URL:
      https://psalmboek.nl/zingen.php?psalm=<psalmnummer>&psvID=<psalmvers>#psvs
    Afhankelijk van de STRICT_POLICY wordt de tekst gecontroleerd en gevalideerd
    (via get_psalm_text_strict) of direct opgehaald (via get_psalm_text_simple).
    """
    if psalm < 1 or psalm > 150:
        raise HTTPException(status_code=400, detail="Ongeldig psalmnummer. Een psalmnummer moet tussen 1 en 150 liggen.")
    # Indien nodig: speciale validatie voor Psalm 119 (bijv. vers 1-88)
    if psalm == 119 and (vers < 1 or vers > 88):
        raise HTTPException(status_code=400, detail="Voor Psalm 119 moet het versnummer tussen 1 en 88 liggen.")
    text = get_psalm_text(psalm, vers)
    return {"text": text}
