#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi import FastAPI, HTTPException, Query
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from functools import lru_cache

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
    Probeer eerst een container met een bekende id of class (bijv. "tekst" of "psalm-tekst") te vinden.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    container = soup.find("div", {"id": "psalm-tekst"})
    if container:
        return container.get_text(strip=True)
    # Fallback: geef de volledige tekst terug
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

def get_psalm_text_liturgie(psalm: int, vers: int) -> str:
    """
    Haal de psalmtekst op via liturgie.nu.
    We gaan ervan uit dat de gehele psalm op de pagina staat via:
       https://www.liturgie.nu/psalmen/<psalmnummer>
    De tekst wordt uit een container met id "psalm-tekst" gelezen (indien aanwezig).
    Vervolgens splitsen we de tekst in regels, waarbij elke regel een vers voorstelt.
    Het gevraagde vers (op basis van het versnummer) wordt geretourneerd.
    """
    base_url = f"https://www.liturgie.nu/psalmen/{psalm}"
    html = cached_get(base_url)
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find("div", {"id": "psalm-tekst"})
    if not container:
        raise HTTPException(status_code=404, detail="Psalmtekst niet gevonden op liturgie.nu")
    # Haal de volledige tekst op en splits op nieuwe regels
    full_text = container.get_text(separator="\n", strip=True)
    verses = [line.strip() for line in full_text.split("\n") if line.strip()]
    if not verses:
        raise HTTPException(status_code=404, detail="Geen verzen gevonden in de psalmtekst")
    if vers < 1 or vers > len(verses):
        raise HTTPException(status_code=400, detail="Ongeldig versnummer")
    return verses[vers - 1]

def get_psalm_text(psalm: int, vers: int) -> str:
    """
    Haal de psalmtekst op. In deze versie gebruiken we liturgie.nu als primaire bron.
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
    psalm: int = Query(..., description="Het psalmnummer (bijv. 120)"),
    vers: int = Query(..., description="Het versnummer binnen de psalm (bijv. 2)"),
    hash: str = Query(None, description="Optioneel anker voor navigatie")
):
    """
    Endpoint voor het ophalen van een psalmvers.
    De tekst wordt opgehaald via liturgie.nu op de pagina:
       https://www.liturgie.nu/psalmen/<psalmnummer>
    en vervolgens wordt het gevraagde vers (op basis van het versnummer) uit de gesplitste tekst geretourneerd.
    """
    if psalm < 1 or psalm > 150:
        raise HTTPException(status_code=400, detail="Ongeldig psalmnummer. Een psalmnummer moet tussen 1 en 150 liggen.")
    text = get_psalm_text(psalm, vers)
    return {"text": text}
