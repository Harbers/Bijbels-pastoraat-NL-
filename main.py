#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi import FastAPI, APIRouter, HTTPException, Query
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin
from functools import lru_cache
import re
import logging

# Stel logging in voor debugging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("psalm_api")

app = FastAPI()

@app.get("/")
def root():
    return {"status": "Bijbels Pastoraat API draait correct"}

api_router = APIRouter(prefix="/api")

STATIC_OUTBOUND_IPS = ["18.156.158.53", "18.156.42.200", "52.59.103.54"]

@lru_cache(maxsize=1024)
def cached_get(url: str) -> str:
    logger.debug(f"Ophalen URL: {url}")
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        logger.debug(f"URL succesvol opgehaald: {url}")
        return response.text
    else:
        logger.error(f"Fout bij ophalen van URL: {url} - Status: {response.status_code}")
        raise HTTPException(status_code=response.status_code,
                            detail=f"Fout bij ophalen van URL: {url}")

def strip_text(html_content: str) -> str:
    soup = BeautifulSoup(html_content, "html.parser")
    container = soup.find("div", {"id": "psalm-tekst"}) or soup.find("div", {"id": "psalmtekst"})
    if container:
        logger.debug("Container voor psalmtekst gevonden.")
        return container.get_text(separator="\n", strip=True)
    logger.debug("Geen specifieke container gevonden, gebruik volledige pagina-tekst.")
    return soup.get_text(separator="\n", strip=True)

def extract_verse(text: str, psalm: int, vers: int) -> str:
    """
    Extraheert het gevraagde vers uit de volledige psalmtekst.
    
    1. Probeer eerst expliciete markers te vinden (losser ingestelde regex’s).
    2. Als dat niet lukt, splits de tekst op newlines.
    3. Als dat te weinig regels oplevert, probeer dan te splitsen op interpunctie (bijv. punt, komma, puntkomma).
    """
    patterns = [
        re.compile(rf'Psalm\s*{psalm}\s*[:\-]\s*{vers}\b', re.IGNORECASE),
        re.compile(rf'Psalm\s*{psalm}\s*vers\s*{vers}\b', re.IGNORECASE),
        re.compile(rf'\bVers\s*[:\-]?\s*{vers}\b', re.IGNORECASE)
    ]
    for pattern in patterns:
        m = pattern.search(text)
        if m:
            start = m.end()
            pattern_next = re.compile(r'\bVers\s*[:\-]?\s*\d+', re.IGNORECASE)
            m_next = pattern_next.search(text, pos=start)
            end = m_next.start() if m_next else len(text)
            verse_text = text[start:end].strip()
            if verse_text:
                logger.debug(f"Marker gevonden met patroon {pattern.pattern}: {verse_text[:60]}...")
                return verse_text

    # Eerste fallback: splitsen op newlines
    lines = re.split(r'\n+', text.strip())
    if len(lines) >= vers:
        logger.debug(f"Nieuwe regels fallback: {len(lines)} regels gevonden.")
        return lines[vers - 1].strip()

    # Tweede fallback: splitsen op interpunctie (punt, komma, puntkomma)
    splits = re.split(r'[.,;]+', text.strip())
    if len(splits) >= vers:
        logger.debug(f"Interpunctie fallback: {len(splits)} segmenten gevonden.")
        return splits[vers - 1].strip()

    raise HTTPException(status_code=400, detail="Ongeldig versnummer of tekststructuur niet herkend.")

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
    unique_url = get_unique_psalm_url(psalm, vers)
    html = cached_get(unique_url)
    full_text = strip_text(html)
    logger.debug(f"Volledige tekst (eerste 200 karakters): {full_text[:200]}...")
    verse_text = extract_verse(full_text, psalm, vers)
    if not verse_text:
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
        full_text = strip_text(html)
        text = extract_verse(full_text, psalm, vers)
        unique_url = None
    else:
        raise HTTPException(status_code=400, detail="Onbekende bronparameter.")
    return {"text": text, "unique_url": unique_url}

app.include_router(api_router, prefix="/api")
