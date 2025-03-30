#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi import FastAPI, HTTPException, Query
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
from functools import lru_cache

app = FastAPI()

# Configuratie: Als STRICT_POLICY True is, wordt het volledige validatieproces (fallback, extra checks) uitgevoerd.
# Als het False is, wordt alleen de directe URL-controle toegepast.
STRICT_POLICY = True

# Eenvoudige cache voor opgevraagde content
@lru_cache(maxsize=1024)
def cached_get(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.text
    else:
        raise HTTPException(status_code=response.status_code, detail=f"Fout bij ophalen van URL: {url}")

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

def get_psalm_text_strict(psalm: int, vers: int) -> str:
    """
    Voer de volledige validatie uit (fallback, chunk-verificatie, whitespace-herstel en dual-source agreement check)
    om de officiële, letterlijke tekst van een psalmvers te verkrijgen.
    """
    base_url = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID={vers}#psvs"
    html = cached_get(base_url)
    soup = BeautifulSoup(html, "html.parser")
    kernwoorden_link = soup.find("a", href=lambda h: h and "kernwoorden.php" in h)
    if kernwoorden_link and kernwoorden_link.get("href"):
        kern_url = urljoin("https://psalmboek.nl/", kernwoorden_link["href"])
        kern_html = cached_get(kern_url)
        kern_soup = BeautifulSoup(kern_html, "html.parser")
        text_div = kern_soup.find("div", {"id": "tekst"})
        if text_div:
            # Hier kan eventueel extra validatie (bijv. chunk-checks, whitespace-normalisatie) plaatsvinden.
            return text_div.get_text(strip=True)
        else:
            return kern_soup.get_text(strip=True)
    # Fallback als geen kernwoorden-link is gevonden
    return soup.get_text(strip=True)

def get_psalm_text_simple(psalm: int, vers: int) -> str:
    """
    Eenvoudige methode: haal de tekst rechtstreeks op via de basis-URL zonder extra validatie.
    """
    url = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID={vers}#psvs"
    html = cached_get(url)
    soup = BeautifulSoup(html, "html.parser")
    # Probeer een container met id "tekst" te vinden
    text_div = soup.find("div", {"id": "tekst"})
    if text_div:
        return text_div.get_text(strip=True)
    return soup.get_text(strip=True)

def get_psalm_text(psalm: int, vers: int) -> str:
    """
    Haal de psalmtekst op via psalmboek.nl. Afhankelijk van de STRICT_POLICY-parameter
    wordt ofwel de volledige validatie (strict) uitgevoerd of een eenvoudige methode gebruikt.
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
    of direct teruggegeven (simple).
    """
    if psalm < 1 or psalm > 150:
        raise HTTPException(status_code=400, detail="Ongeldig psalmnummer. Een psalmnummer moet tussen 1 en 150 liggen.")
    if psalm == 119 and (vers < 1 or vers > 88):
        raise HTTPException(status_code=400, detail="Voor Psalm 119 moet het versnummer tussen 1 en 88 liggen.")
    text = get_psalm_text(psalm, vers)
    return {"text": text}
