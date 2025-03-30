#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import requests
import logging
import time
from fastapi import FastAPI, APIRouter, HTTPException, Query
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin
from functools import lru_cache

# Probeer Selenium te importeren; als dit mislukt, schakelen we Selenium-fallback uit.
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logging.warning("Selenium is niet geïnstalleerd; Selenium-fallback zal niet werken.")

# Configureer logging op debug-niveau
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("psalm_api")

app = FastAPI()

@app.get("/")
def root():
    return {"status": "Bijbels Pastoraat API draait correct"}

# Maak de API-router zonder vooraf ingestelde prefix; we voegen deze later toe.
api_router = APIRouter()

STATIC_OUTBOUND_IPS = ["18.156.158.53", "18.156.42.200", "52.59.103.54"]

# Interne mapping voor berijmde psalmen (voorbeeld)
BERIJMD_VERZEN = {
    119: 50,
    138: 1
}

@lru_cache(maxsize=1024)
def cached_get(url: str) -> str:
    logger.debug(f"Ophalen URL: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        logger.debug(f"URL succesvol opgehaald: {url}")
        return response.text
    else:
        logger.error(f"Fout bij ophalen van URL: {url} - Status: {response.status_code}")
        raise HTTPException(status_code=response.status_code, detail=f"Fout bij ophalen van URL: {url}")

def strip_text(html_content: str) -> str:
    soup = BeautifulSoup(html_content, "html.parser")
    container = soup.find("div", {"id": "psalm-tekst"}) or soup.find("div", {"id": "psalmtekst"})
    if container:
        logger.debug("Container voor psalmtekst gevonden.")
        return container.get_text(separator="\n", strip=True)
    logger.debug("Geen specifieke container gevonden, gebruik volledige pagina-tekst.")
    return soup.get_text(separator="\n", strip=True)

def extract_structured_verses(html_content: str) -> dict:
    soup = BeautifulSoup(html_content, "html.parser")
    verse_divs = soup.find_all("div", class_="vers belijdenis_inhoud line_breaks ritmisch")
    verses = {}
    if verse_divs:
        logger.debug(f"Gestructureerde extractie: {len(verse_divs)} divs gevonden.")
        for div in verse_divs:
            vers_tag = div.find("a", class_="versnummer")
            if vers_tag:
                try:
                    vers_no = int(vers_tag.get_text(strip=True))
                except ValueError:
                    continue
            else:
                continue
            p_tag = div.find("p", class_="verstekst")
            if p_tag:
                verse_text = p_tag.get_text(separator="\n", strip=True)
                verses[vers_no] = verse_text
        logger.debug(f"Extracted verses via structuur: {list(verses.keys())}")
    return verses

def extract_verse_fallback(text: str, psalm: int, vers: int) -> str:
    lines = re.split(r'\n+', text.strip())
    logger.debug(f"Fallback 1 (newline-splitsing): {len(lines)} regels gevonden.")
    if len(lines) >= vers:
        return lines[vers - 1].strip()
    soup = BeautifulSoup(text, "html.parser")
    br_text = soup.get_text(separator="\n", strip=True)
    br_lines = br_text.split("\n")
    logger.debug(f"Fallback 2 (<br>-splitsing): {len(br_lines)} regels gevonden.")
    if len(br_lines) >= vers:
        return br_lines[vers - 1].strip()
    raise HTTPException(status_code=400, detail="Ongeldig versnummer of tekststructuur niet herkend in fallback.")

def extract_verse_from_html(html_content: str, psalm: int, vers: int) -> str:
    verses = extract_structured_verses(html_content)
    if verses and vers in verses:
        extracted = verses[vers].strip()
        logger.debug(f"Gestructureerde extractie succesvol voor vers {vers}: {extracted[:60]}...")
        if len(extracted) < 10 or extracted.strip().lower() in ["psalmen", "zingen"]:
            logger.debug(f"Extractie geeft onvolledige tekst ('{extracted}'), overschakelen naar fallback.")
            full_text = strip_text(html_content)
            logger.debug("Volledige tekst snippet: " + full_text[:500])
            return extract_verse_fallback(full_text, psalm, vers)
        return extracted
    else:
        logger.debug("Gestructureerde extractie mislukt, gebruik fallback-methode.")
        text = strip_text(html_content)
        return extract_verse_fallback(text, psalm, vers)

# Functie om de Psalm-tekst via een statische pagina van Psalmboek.nl op te halen
def get_psalm_text_psalmboek(psalm: int, vers: int) -> str:
    base_url = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID={vers}#psvs"
    html = cached_get(base_url)
    logger.debug("HTML snippet: " + html[:500])
    try:
        verse_text = extract_verse_from_html(html, psalm, vers)
    except HTTPException:
        logger.debug("Reguliere extractie mislukt, probeer Selenium fallback.")
        verse_text = extract_text_via_selenium(base_url)
    if not verse_text or verse_text.strip().lower() in ["psalmen", "zingen"]:
        logger.debug(f"Extractie geeft onvolledige tekst ('{verse_text}'), overschakelen naar alternatieve fallback.")
        full_text = strip_text(html)
        logger.debug("Volledige tekst snippet: " + full_text[:500])
        try:
            verse_text = extract_verse_fallback(full_text, psalm, vers)
        except Exception as e:
            logger.error("Alternatieve fallback mislukt: " + str(e))
            raise HTTPException(status_code=404, detail="Psalmvers niet gevonden via psalmboek.nl")
    return verse_text

# Functie voor het ophalen van de tekst van de bijbelvers
def get_bible_text(book: str, chapter: int, verse: int) -> str:
    url = f"https://www.statenvertaling.net/bijbel/{quote(book)}/{chapter}/{verse}"
    html = cached_get(url)
    text = strip_text(html)
    if not text:
        raise HTTPException(status_code=404, detail="Bijbeltekst niet gevonden.")
    return text

# API-endpoints
@api_router.get("/bible/{book}/{chapter}/{verse}")
def bible_endpoint(book: str, chapter: int, verse: int):
    text = get_bible_text(book, chapter, verse)
    return {"text": text}

@api_router.get("/psalm")
def psalm_endpoint(
    psalm: int = Query(..., description="Het psalmnummer (1 t/m 150)"),
    vers: int = Query(..., description="Het versnummer binnen de psalm"),
    source: str = Query("psalmboek", description="Bron: 'psalmboek' of 'onlinebijbel'")
):
    if psalm < 1 or psalm > 150:
        raise HTTPException(status_code=400, detail="Ongeldig psalmnummer. Een psalmnummer moet tussen 1 en 150 liggen.")
    if source.lower() == "psalmboek":
        text = get_psalm_text_psalmboek(psalm, vers)
        unique_url = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID={vers}#psvs"
    elif source.lower() == "onlinebijbel":
        base_url = f"https://www.online-bijbel.nl/psalm/{psalm}"
        html = cached_get(base_url)
        text = extract_verse_from_html(html, psalm, vers)
        unique_url = None
    else:
        raise HTTPException(status_code=400, detail="Onbekende bronparameter.")
    return {"text": text, "unique_url": unique_url}

# Voeg de API-router toe met de prefix "/api"
app.include_router(api_router, prefix="/api")
