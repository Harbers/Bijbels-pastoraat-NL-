from fastapi import FastAPI, HTTPException

app = FastAPI()

def scrape_psalmboek(psalm, vers):
    # TODO: Voeg echte scraping-code toe voor psalmboek.nl
    # Voorbeeld dummy return:
    if psalm == 103 and vers == 8:
        return "Gelijk het gras is ons kortstondig leven, Gelijk een bloem, die op het veld verheven, ..."
    return None

def scrape_liturgie(psalm, vers):
    # TODO: Voeg echte scraping-code toe voor liturgie.nu
    return None

def scrape_bijbelbox(psalm, vers):
    # TODO: Voeg echte scraping-code toe voor bijbelbox.nl
    return None

def zoek_berijmd_vers(psalm, vers):
    tekst = scrape_psalmboek(psalm, vers)
    if tekst:
        return tekst, "psalmboek.nl"
    tekst = scrape_liturgie(psalm, vers)
    if tekst:
        return tekst, "liturgie.nu"
    tekst = scrape_bijbelbox(psalm, vers)
    if tekst:
        return tekst, "bijbelbox.nl"
    return None, None

@app.get("/psalm")
def get_psalm_text(psalm: int, vers: int):
    tekst, bron = zoek_berijmd_vers(psalm, vers)
    if tekst:
        return {"text": tekst, "bron": bron}
    raise HTTPException(status_code=404, detail="Vers niet gevonden bij de drie externe bronnen.")
