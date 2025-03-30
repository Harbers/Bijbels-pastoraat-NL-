#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import requests
import logging
from fastapi import FastAPI, APIRouter, HTTPException, Query
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin
from functools import lru_cache

# Configureer logging op debug-niveau
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("psalm_api")

app = FastAPI()

@app.get("/")
def root():
    return {"status": "Bijbels Pastoraat API draait correct"}

api_router = APIRouter(prefix="/api")

STATIC_OUTBOUND_IPS = ["18.156.158.53", "18.156.42.200", "52.59.103.54"]

# Interne mapping voor berijmde psalmen (voorbeeld)
BERIJMD_VERZEN = {
    119: 50,
    138: 1
}

@lru_cache(maxsize=1024)
def cached_get(url: str) -> str:
    logger.debug(f"Ophalen URL: {url}")
    # Extra headers om een echte browser na te bootsen
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
    """
    Bouwt een mapping op van versnummers naar tekst, gebaseerd op div's met de klasse
    'vers belijdenis_inhoud line_breaks ritmisch'.
    """
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
                verse_text = p_tag.get_text(separator=" ", strip=True)
                verses[vers_no] = verse_text
        logger.debug(f"Extracted verses via structuur: {list(verses.keys())}")
    return verses

def extract_verse_fallback(text: str, psalm: int, vers: int) -> str:
    """
    Fallback-extractie: splits eerst op newlines; indien onvoldoende, splits op <br>-elementen.
    """
    lines = re.split(r'\n+', text.strip())
    logger.debug(f"Fallback 1 (newline-splitsing): {len(lines)} regels gevonden.")
    if len(lines) >= vers:
        return lines[vers - 1].strip()
    # Tweede fallback: gebruik BeautifulSoup om <br>-tags te verwerken
    soup = BeautifulSoup(text, "html.parser")
    br_text = soup.get_text(separator="\n", strip=True)
    br_lines = br_text.split("\n")
    logger.debug(f"Fallback 2 (<br>-splitsing): {len(br_lines)} regels gevonden.")
    if len(br_lines) >= vers:
        return br_lines[vers - 1].strip()
    raise HTTPException(status_code=400, detail="Ongeldig versnummer of tekststructuur niet herkend.")

def extract_verse_from_html(html_content: str, psalm: int, vers: int) -> str:
    verses = extract_structured_verses(html_content)
    if verses and vers in verses:
        logger.debug(f"Gestructureerde extractie succesvol voor vers {vers}: {verses[vers][:60]}...")
        return verses[vers]
    else:
        logger.debug("Gestructureerde extractie mislukt, gebruik fallback-methode.")
        text = strip_text(html_content)
        return extract_verse_fallback(text, psalm, vers)

def get_unique_psalm_url(psalm: int, vers: int) -> str:
    base_url = f"https://psalmboek.nl/zingen.php?psalm={psalm}&psvID={vers}#psvs"
    html = cached_get(base_url)
    soup = BeautifulSoup(html, "html.parser")
    link = soup.find("a", href=lambda h: h and "kernwoorden.php" in h)
    if link and link.get("href"):
        unique_url = urljoin("https://psalmboek.nl/", link["href"])
        logger.debug(f"Uniek URL gevonden: {unique_url}")
        return unique_url
    logger.debug("Geen uniek URL gevonden, standaard URL gebruiken.")
    return base_url

def get_psalm_text_psalmboek(psalm: int, vers: int) -> str:
    if psalm in BERIJMD_VERZEN and vers > BERIJMD_VERZEN[psalm]:
        raise HTTPException(status_code=400, detail=f"Psalm {psalm} bevat in de berijmde versie slechts {BERIJMD_VERZEN[psalm]} verzen.")
    unique_url = get_unique_psalm_url(psalm, vers)
    html = cached_get(unique_url)
    verse_text = extract_verse_from_html(html, psalm, vers)
    if not verse_text:
        logger.error("Geen psalmvers gevonden na extractie.")
        raise HTTPException(status_code=404, detail="Psalmvers niet gevonden via psalmboek.nl")
    return verse_text

def get_bible_text(book: str, chapter: int, verse: int) -> str:
    url = f"https://www.statenvertaling.net/bijbel/{quote(book)}/{chapter}/{verse}"
    html = cached_get(url)
    text = strip_text(html)
    if not text:
        raise HTTPException(status_code=404, detail="Bijbeltekst niet gevonden.")
    return text

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
        unique_url = get_unique_psalm_url(psalm, vers)
    elif source.lower() == "onlinebijbel":
        base_url = f"https://www.online-bijbel.nl/psalm/{psalm}"
        html = cached_get(base_url)
        text = extract_verse_from_html(html, psalm, vers)
        unique_url = None
    else:
        raise HTTPException(status_code=400, detail="Onbekende bronparameter.")
    return {"text": text, "unique_url": unique_url}

app.include_router(api_router, prefix="/api")
