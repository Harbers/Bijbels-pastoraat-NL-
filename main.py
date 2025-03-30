#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi import FastAPI, HTTPException, Query
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
from functools import lru_cache

app = FastAPI()

# Configuratie: Als STRICT_POLICY True is, wordt de uitgebreide validatie (met fallback en extra checks) uitgevoerd.
STRICT_POLICY = True

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
    Verwerk de HTML-content en retourneer de 'gestript' tekst.
    Eerst wordt geprobeerd een container met id "tekst" of "psalmtekst" te vinden.
    Als deze niet wordt gevonden, wordt de volledige tekst van de pagina teruggegeven,
    met overtollige whitespace verwijderd.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    # Probeer eerst een container met id "tekst"
    container = soup.find("div", {"id": "tekst"})
    if container:
        return container.get_text(strip=True)
    # Probeer een container met id "psalmtekst"
    container = soup.find("div", {"id": "psalmtekst"})
    if container:
        return container.get_text(strip=True)
    # Als geen specifieke container gevonden is, haal dan de volledige tekst op
    return soup.get_text(strip=True)

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

def get_psalm_text_strict(psalm: int, vers: int) -> str:
    """
    Voer het volledige validatieproces uit: 
      - Haal eerst de standaardpagina op met de basis-URL inclusief anker "#psvs".
      - Zoek naar een link naar de 'kernwoorden.php'-weergave en gebruik deze als deze aanwezig is.
      - Pas de strip_text-methode toe om de relevante tekst (bijvoorbeeld onder de kop “Psalm <psalm> vers <vers>”) te extraheren.
    """
    base_url = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID={vers}#psvs"
    html = cached_get(base_url)
    soup = BeautifulSoup(html, "html.parser")
    
    # Zoek naar een link met 'kernwoorden.php' in de href
    kernwoorden_link = soup.find("a", href=lambda h: h and "kernwoorden.php" in h)
    if kernwoorden_link and kernwoorden_link.get("href"):
        kern_url = urljoin("https://psalmboek.nl/", kernwoorden_link["href"])
        kern_html = cached_get(kern_url)
        text = strip_text(kern_html)
        if text:
            return text
        else:
            return kern_html  # fallback indien strip_text niets oplevert
    # Fallback: gebruik de tekst van de oorspronkelijke pagina
    return strip_text(html)

def get_psalm_text_simple(psalm: int, vers: int) -> str:
    """
    Eenvoudige methode: haal de tekst rechtstreeks op via de basis-URL zonder extra validatie.
    """
    url = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID={vers}#psvs"
    html = cached_get(url)
    return strip_text(html)

def get_psalm_text(psalm: int, vers: int) -> str:
    """
    Haal de psalmtekst op via psalmboek.nl. Afhankelijk van de STRICT_POLICY wordt
    ofwel de volledige validatie (strict) uitgevoerd of een eenvoudige methode toegepast.
    """
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
    Afhankelijk van de STRICT_POLICY wordt de tekst gecontroleerd en gevalideerd (strict)
    of direct teruggegeven (simple). De functie gebruikt de 'strip_text'-methode om de
    relevante tekst uit de HTML te halen.
    """
    if psalm < 1 or psalm > 150:
        raise HTTPException(status_code=400, detail="Ongeldig psalmnummer. Een psalmnummer moet tussen 1 en 150 liggen.")
    # Specifieke validatie voor Psalm 119 indien gewenst (bijv. vers 1-88)
    if psalm == 119 and (vers < 1 or vers > 88):
        raise HTTPException(status_code=400, detail="Voor Psalm 119 moet het versnummer tussen 1 en 88 liggen.")
    text = get_psalm_text(psalm, vers)
    return {"text": text}
