#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi import FastAPI, HTTPException, Query
import os
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import quote

app = FastAPI()

@app.get("/")
def root():
    return {"status": "Backend API is actief"}

def get_bible_text(book: str, chapter: int, verse: int) -> str:
    # Haal de bijbeltekst op via een externe bron (Statenvertaling, Jongbloed-editie)
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
    Haal de psalmtekst op via een fallback-bron (bijbelbox.nl) en geef het gewenste vers terug.
    """
    url = f"https://www.bijbelbox.nl/psalmen/psalm-{psalm}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, 
                            detail="Fout bij ophalen van de psalmtekst (fallback bron).")
    soup = BeautifulSoup(response.text, "html.parser")
    text_div = soup.find("div", {"id": "psalmtekst"})
    if text_div:
        text_full = text_div.get_text(separator="\n", strip=True)
    else:
        text_full = soup.get_text(separator="\n", strip=True)
    verses = [line.strip() for line in text_full.splitlines() if line.strip()]
    if vers < 1 or vers > len(verses):
        raise HTTPException(status_code=400, detail=f"Versnummer {vers} is ongeldig. Deze psalm heeft {len(verses)} verzen.")
    return verses[vers-1]

def get_psalm_text(psalm: int, vers: int) -> str:
    """
    Probeer eerst de psalmtekst op te halen via de primaire externe bron (liturgie.nu).
    Bij falen wordt de fallback-bron (bijbelbox.nl) gebruikt.
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
        # Normaliseer de tekst
        lines = [re.sub(r'\s+', ' ', line) for line in text.splitlines()]
        normalized_text = "\n".join(lines)
        if not normalized_text.strip():
            return get_psalm_text_fallback(psalm, vers)
        return normalized_text
    else:
        return get_psalm_text_fallback(psalm, vers)

@app.get("/bible/{book}/{chapter}/{verse}")
def bible_endpoint(book: str, chapter: int, verse: int):
    """
    Haal een bijbeltekst op uit de externe bron (Statenvertaling, Jongbloed-editie).
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
    Haal een psalmvers op via een primaire externe bron (liturgie.nu) met fallback naar bijbelbox.nl.
    """
    if psalm < 1 or psalm > 150:
        raise HTTPException(status_code=400, detail="Ongeldig psalmnummer. Een psalmnummer moet tussen 1 en 150 liggen.")
    if psalm == 119 and (vers < 1 or vers > 88):
        raise HTTPException(status_code=400, detail="Voor Psalm 119 moet het versnummer tussen 1 en 88 liggen.")
    text = get_psalm_text(psalm, vers)
    return {"text": text}
