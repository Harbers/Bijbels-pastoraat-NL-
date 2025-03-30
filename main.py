#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi import FastAPI, HTTPException, Query
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
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

def strip_text(html_content: str) -> str:
    """
    Verwerk de HTML-content en retourneer de 'gestript' tekst.
    Eerst wordt gezocht naar een container met id 'psalm-tekst' (of een vergelijkbare id).
    Als deze container niet wordt gevonden, wordt de volledige pagina-tekst gebruikt.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    container = soup.find("div", {"id": "psalm-tekst"})
    if container:
        return container.get_text(separator="\n", strip=True)
    # Fallback: retourneer de gehele pagina-tekst
    return soup.get_text(separator="\n", strip=True)

def extract_verse(text: str, psalm: int, vers: int) -> str:
    """
    Probeer eerst de tekst te splitsen op herkenningspunten (bijvoorbeeld headers met 'Psalm <psalm> vers <nummer>')
    en gebruik deze als anker om de juiste grens te bepalen.
    Als dat niet lukt, splits dan op nieuwe regels en neem de regel die overeenkomt met het versnummer.
    """
    # Zoek naar een patroon: "Psalm <psalm> vers <nummer>"
    pattern = re.compile(rf'Psalm\s*{psalm}\s*vers\s*(\d+)', re.IGNORECASE)
    matches = list(pattern.finditer(text))
    if matches:
        # Als markers aanwezig zijn, bepaal dan de begin- en eindindex van het gewenste vers.
        verses_found = {}
        for i, m in enumerate(matches):
            try:
                verse_num = int(m.group(1))
                # Bepaal de startindex van dit vers
                start = m.end()
                # De eindindex is de start van de volgende marker, of het einde van de tekst.
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                verses_found[verse_num] = text[start:end].strip()
            except (IndexError, ValueError):
                continue
        if vers in verses_found and verses_found[vers]:
            return verses_found[vers]
    # Fallback: splits op nieuwe regels en neem de corresponderende regel
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if 1 <= vers <= len(lines):
        return lines[vers - 1]
    raise HTTPException(status_code=400, detail="Ongeldig versnummer of tekststructuur niet herkend.")

def get_psalm_text_liturgie(psalm: int, vers: int) -> str:
    """
    Haal de volledige psalmtekst op via liturgie.nu en extraheer het gewenste vers.
    We gaan ervan uit dat de psalm op de URL:
       https://www.liturgie.nu/psalmen/<psalmnummer>
    staat en dat de tekst in een container met id 'psalm-tekst' staat.
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

def get_psalm_text(psalm: int, vers: int) -> str:
    """
    Universele methode voor het ophalen van een psalmvers via liturgie.nu.
    """
    return get_psalm_text_liturgie(psalm, vers)

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
    Endpoint voor het ophalen van een psalmvers via liturgie.nu.
    De psalmtekst wordt opgehaald via:
       https://www.liturgie.nu/psalmen/<psalmnummer>
    en vervolgens wordt het gevraagde vers (op basis van het versnummer) geëxtraheerd.
    """
    if psalm < 1 or psalm > 150:
        raise HTTPException(status_code=400, detail="Ongeldig psalmnummer. Een psalmnummer moet tussen 1 en 150 liggen.")
    text = get_psalm_text(psalm, vers)
    return {"text": text}
