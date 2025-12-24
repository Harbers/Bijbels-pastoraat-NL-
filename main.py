from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse, Response, HTMLResponse

from schemas import PsalmVersResponse, PsalmMaxResponse
from config import settings
from psalms import client

app = FastAPI(
    title="Bijbels-Pastoraat-NL Backend",
    version="1.0.0",
    description="API voor berijmde psalmverzen (1773) via psalmboek.nl",
    contact={"name": "Bijbels-Pastoraat-NL", "email": "support@bijbels-pastoraat-nl.onrender.com"},
    license_info={"name": "MIT"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://chat.openai.com",
        "https://gpt-harbers.duckdns.org",
        "http://gpt-harbers.duckdns.org",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")

@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "ok"}

OPENAPI_YAML = """openapi: 3.1.0
info:
  title: Bijbels-Pastoraat-NL Backend
  version: "1.0.0"
  description: |
    API voor berijmde psalmverzen (1773) via psalmboek.nl
servers:
  - url: https://gpt-harbers.duckdns.org
paths:
  /api/psalm/vers:
    get:
      summary: Haal exact één vers op uit berijming 1773
      operationId: get_berijmd_psalmvers
      parameters:
        - in: query
          name: psalm
          required: true
          schema: { type: integer, minimum: 1, maximum: 150 }
        - in: query
          name: vers
          required: true
          schema: { type: integer, minimum: 1 }
      responses:
        "200": { description: Succes }
        "400": { description: Buiten bereik of niet gevonden }
        "404": { description: Niet gevonden }
        "502": { description: Fout bij bron }
  /api/psalm/max:
    get:
      summary: Max vers
      operationId: get_psalm_max
      parameters:
        - in: query
          name: psalm
          required: true
          schema: { type: integer, minimum: 1, maximum: 150 }
      responses:
        "200": { description: Succes }
        "502": { description: Fout bij bron }
"""
@app.get("/openapi.yaml", include_in_schema=False)
def openapi_yaml():
    return Response(content=OPENAPI_YAML, media_type="application/yaml")

@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
def manifest():
    return JSONResponse({
        "schema_version": "v1",
        "name_for_human": "Bijbels-Pastoraat-NL",
        "name_for_model": "bijbels_pastoraat",
        "description_for_human": "Haal psalmverzen op uit de officiële berijming van 1773.",
        "description_for_model": (
            "Ultrakorte System Prompt – Bijbelse Pastorale Zorg (SV + Psalmen 1773). "
            "Start met de vraag: 'Hoe mag ik je noemen, zodat ik persoonlijk met je kan spreken?' en wacht op antwoord. "
            "Gebruik nl_Statenvertaling.txt voor onberijmde Bijbelteksten; citeer exact, geen parafrase. "
            "Voor berijmde psalmen en gezangen gebruik altijd de plugin bijbels_pastoraat.get_berijmd_psalmvers "
            "(GET /api/psalm/vers). Toon uitsluitend plugin-JSON; plugin-fout: 'Vers <x> van Psalm <y> kon niet worden opgehaald.' "
            "Reflecties: gereformeerd, Christus-centraal, warm en respectvol; zes open vragen bij pastorale begeleiding, "
            "minstens twee maatschappelijk. Geen handelingen namens God; verwijs naar belijdenis.nu."
        ),
        "auth": {"type": "none"},
        "api": {"type": "openapi", "url": "https://gpt-harbers.duckdns.org/openapi.yaml", "is_user_authenticated": False},
        "logo_url": "https://gpt-harbers.duckdns.org/static/logo.svg",
        "contact_email": "support@bijbels-pastoraat-nl.onrender.com",
        "legal_info_url": "https://gpt-harbers.duckdns.org/legal"
    })

SVG_LOGO = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256">
  <rect width="256" height="256" fill="#f2f2f2"/>
  <text x="50%" y="50%" dy="8" text-anchor="middle" font-family="Georgia" font-size="28">1773</text>
</svg>
"""
@app.get("/static/logo.svg", include_in_schema=False)
def logo_svg():
    return Response(content=SVG_LOGO, media_type="image/svg+xml")

@app.get("/legal", include_in_schema=False, response_class=HTMLResponse)
def legal():
    return "<h1>Privacybeleid</h1><p>Geen persoonsgegevens worden opgeslagen.</p>"

# --- API ---------------------------------------------------------------------

@app.get("/api/psalm/max", response_model=PsalmMaxResponse)
def get_psalm_max(psalm: int = Query(..., ge=1, le=150)):
    try:
        max_vers = client.get_max_vers(psalm)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Fout bij ophalen bron: {e}")
    return PsalmMaxResponse(
        psalm=psalm,
        max_vers=max_vers,
        bron=f"{settings.PSALM_SOURCE_BASE}/psalmen.php?berijming={client.berijming}&psalm={psalm}",
    )

@app.get("/api/psalm/vers", response_model=PsalmVersResponse)
def get_psalm_vers(psalm: int = Query(..., ge=1, le=150), vers: int = Query(..., ge=1)):
    try:
        max_vers = client.get_max_vers(psalm)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Fout bij ophalen bron: {e}")

    if vers > max_vers:
        raise HTTPException(status_code=400, detail=f"Vers {vers} van Psalm {psalm} kon niet worden opgehaald.")

    try:
        text = client.get_vers(psalm, vers)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Vers {vers} van Psalm {psalm} kon niet worden opgehaald.")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Fout bij ophalen bron: {e}")

    return PsalmVersResponse(
        psalm=psalm,
        vers=vers,
        text=text,
        bron=f"{settings.PSALM_SOURCE_BASE}/psalmen.php?berijming={client.berijming}&psalm={psalm}#{vers}",
    )
