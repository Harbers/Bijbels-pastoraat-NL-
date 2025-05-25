
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from bs4 import BeautifulSoup
import requests

app = FastAPI()

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def extract_vers_psalmboek(psalm: int, vers: int) -> str:
    print(f"[extract_vers_psalmboek] Opvragen vers voor Psalm {psalm}, vers {vers}")
    url = f"https://psalmboek.nl/psalm/{psalm}/{vers}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"[extract_vers_psalmboek] Fout bij ophalen pagina: {e}")
        return "Fout bij ophalen pagina"

    html = response.text
    print(f"[extract_vers_psalmboek] Eerste 500 tekens HTML: {html[:500]}")
    soup = BeautifulSoup(html, "html.parser")
    blok = soup.find(id="psvs")
    if blok is None:
        print("[extract_vers_psalmboek] ID 'psvs' niet gevonden in HTML")
        return "Geen vers gevonden - container ontbreekt"

    tekst = blok.get_text(strip=True)
    print(f"[extract_vers_psalmboek] Gevonden tekst: {tekst}")
    return tekst or "Vers bestaat mogelijk niet"

@app.get("/psalm")
def get_psalm_text(psalm: int, vers: int, hash: str = None):
    tekst = extract_vers_psalmboek(psalm, vers)
    if not tekst or "Fout" in tekst or "geen" in tekst.lower():
        raise HTTPException(status_code=404, detail="Vers niet gevonden")
    return {"text": tekst}

@app.get("/debug/vers")
def debug_vers(psalm: int, vers: int):
    tekst = extract_vers_psalmboek(psalm, vers)
    if not tekst:
        raise HTTPException(status_code=404, detail="Vers niet gevonden")
    return {"tekst": tekst}
