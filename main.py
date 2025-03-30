#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi import FastAPI, HTTPException, Query
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

app = FastAPI()

@app.get("/")
def root():
    return {"status": "Backend API is actief"}

def get_bible_text(book: str, chapter: int, verse: int) -> str:
    """
    Haal de bijbeltekst op via een externe bron (Statenvertaling, Jongbloed-editie).
    """
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

def get_psalm_text(psalm: int, vers: int) -> str:
    """
    Haal de psalmtekst op via de externe bron psalmboek.nl.
    Er wordt de URL gebruikt in het formaat:
      https://psalmboek.nl/zingen.php?psalm=<psalmnummer>&psvID=<psalmvers>
    De hoofdtekst van het vers wordt direct opgehaald uit de HTML.
    """
    url = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID={vers}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        # Probeer de container met de verstekst te vinden.
        # Vaak staat de hoofdtekst in een <div> met id "tekst" of in een <article>.
        text_div = soup.find("div", {"id": "tekst"})
        if text_div:
            return text_div.get_text(strip=True)
        article = soup.find("article")
        if article:
            return article.get_text(strip=True)
        # Als er geen specifieke container gevonden is, geef dan de volledige HTML terug.
        return response.text
    else:
        raise HTTPException(status_code=response.status_code, detail="Fout bij ophalen van de psalmtekst.")

@app.get("/bible/{book}/{chapter}/{verse}")
def bible_endpoint(book: str, chapter: int, verse: int):
    """
    Endpoint voor het ophalen van een bijbeltekst uit de externe bron (Statenvertaling, Jongbloed-editie).
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
    De tekst wordt opgehaald via de externe bron psalmboek.nl met de URL-structuur:
      https://psalmboek.nl/zingen.php?psalm=<psalmnummer>&psvID=<psalmvers>
    """
    if psalm < 1 or psalm > 150:
        raise HTTPException(status_code=400, detail="Ongeldig psalmnummer. Een psalmnummer moet tussen 1 en 150 liggen.")
    if psalm == 119 and (vers < 1 or vers > 88):
        raise HTTPException(status_code=400, detail="Voor Psalm 119 moet het versnummer tussen 1 en 88 liggen.")
    text = get_psalm_text(psalm, vers)
    return {"text": text}
