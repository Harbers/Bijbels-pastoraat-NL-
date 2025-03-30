#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi import FastAPI, HTTPException, Query
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
from functools import lru_cache

app = FastAPI()

# Eenvoudige cache voor opgevraagde psalmverzen
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

def get_psalm_text(psalm: int, vers: int) -> str:
    """
    Haal de psalmtekst op via psalmboek.nl met de aangepaste basis-URL:
      https://psalmboek.nl/zingen.php?psalm=<psalmnummer>&psvID=<psalmvers>#psvs
    Eerst wordt de standaardpagina opgehaald en daarna gezocht naar een link
    naar de 'kernwoorden.php'-weergave. Als deze beschikbaar is, wordt de
    officiële tekst (onder de kop "Psalm <psalm> vers <vers>") opgehaald.
    Als de link ontbreekt, gebruiken we de tekst van de oorspronkelijke pagina.
    """
    base_url = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID={vers}#psvs"
    html = cached_get(base_url)
    soup = BeautifulSoup(html, "html.parser")
    
    # Zoek naar een <a>-tag met 'kernwoorden.php' in de href
    kernwoorden_link = soup.find("a", href=lambda h: h and "kernwoorden.php" in h)
    if kernwoorden_link and kernwoorden_link.get("href"):
        kern_url = urljoin("https://psalmboek.nl/", kernwoorden_link["href"])
        kern_html = cached_get(kern_url)
        kern_soup = BeautifulSoup(kern_html, "html.parser")
        # Probeer de container te vinden waarin de letterlijke tekst staat (bijvoorbeeld met id "tekst")
        text_div = kern_soup.find("div", {"id": "tekst"})
        if text_div:
            return text_div.get_text(strip=True)
        else:
            return kern_soup.get_text(strip=True)
    
    # Fallback: gebruik de tekst van de oorspronkelijke pagina
    return soup.get_text(strip=True)

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
    De tekst wordt opgehaald via de aangepaste basis-URL:
      https://psalmboek.nl/zingen.php?psalm=<psalmnummer>&psvID=<psalmvers>#psvs
    Vervolgens wordt er gezocht naar de link naar de 'kernwoorden.php'-weergave om
    de officiële, letterlijke tekst (onder de kop "Psalm <psalm> vers <vers>") te retourneren.
    Indien deze link niet beschikbaar is, wordt de tekst van de oorspronkelijke pagina gebruikt.
    """
    if psalm < 1 or psalm > 150:
        raise HTTPException(status_code=400, detail="Ongeldig psalmnummer. Een psalmnummer moet tussen 1 en 150 liggen.")
    if psalm == 119 and (vers < 1 or vers > 88):
        raise HTTPException(status_code=400, detail="Voor Psalm 119 moet het versnummer tussen 1 en 88 liggen.")
    text = get_psalm_text(psalm, vers)
    return {"text": text}
