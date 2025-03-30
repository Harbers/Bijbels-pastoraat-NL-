#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi import FastAPI, HTTPException, Query
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote

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
        raise HTTPException(status_code=response.status_code,
                            detail="Fout bij ophalen van de bijbeltekst.")
    soup = BeautifulSoup(response.text, "html.parser")
    text_div = soup.find("div", {"id": "tekst"})
    if not text_div:
        raise HTTPException(status_code=404, detail="Bijbeltekst niet gevonden.")
    return text_div.get_text(strip=True)

def get_psalm_text(psalm: int, vers: int) -> str:
    """
    Haal de psalmtekst op via psalmboek.nl. Eerst wordt de standaardpagina (zingen.php)
    geraadpleegd, waarna er wordt gezocht naar een link naar de 'kernwoorden.php'-weergave.
    Als deze link aanwezig is, wordt de tekst rechtstreeks daaruit gehaald (waar de kop 
    "Psalm <psalm> vers <vers>" staat). Als er geen kernwoorden-link wordt gevonden,
    wordt de volledige tekst van de oorspronkelijke pagina gebruikt.
    Deze methode geldt voor alle psalmen en verzen.
    """
    base_url = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID={vers}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(base_url, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code,
                            detail="Fout bij ophalen van de psalmtekst (zingen.php).")
    soup = BeautifulSoup(response.text, "html.parser")
    # Zoek naar een <a>-tag waarvan de href "kernwoorden.php" bevat
    kernwoorden_link = soup.find("a", href=lambda h: h and "kernwoorden.php" in h)
    if kernwoorden_link and kernwoorden_link.get("href"):
        # Maak de URL absoluut indien nodig
        kern_url = urljoin("https://psalmboek.nl/", kernwoorden_link["href"])
        kern_response = requests.get(kern_url, headers=headers)
        if kern_response.status_code == 200:
            kern_soup = BeautifulSoup(kern_response.text, "html.parser")
            # Probeer de tekst te vinden in een container met id "tekst"
            text_div = kern_soup.find("div", {"id": "tekst"})
            if text_div:
                return text_div.get_text(strip=True)
            else:
                # Als geen specifieke container gevonden, geef de volledige tekst terug
                return kern_soup.get_text(strip=True)
    # Fallback: gebruik de tekst van de oorspronkelijke zinnen-pagina
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
    Eerst wordt de pagina https://psalmboek.nl/zingen.php?psalm=<psalm>&psvID=<vers>
    geraadpleegd en daarna wordt gezocht naar de link naar de 'kernwoorden.php'-weergave.
    Als deze beschikbaar is, wordt de hoofdtekst (rechtstreeks onder de kop "Psalm <psalm>
    vers <vers>") opgehaald en geretourneerd.
    """
    if psalm < 1 or psalm > 150:
        raise HTTPException(status_code=400, detail="Ongeldig psalmnummer. Een psalmnummer moet tussen 1 en 150 liggen.")
    # Specifieke validatie voor Psalm 119 indien gewenst (bijv. vers 1-88)
    if psalm == 119 and (vers < 1 or vers > 88):
        raise HTTPException(status_code=400, detail="Voor Psalm 119 moet het versnummer tussen 1 en 88 liggen.")
    text = get_psalm_text(psalm, vers)
    return {"text": text}
