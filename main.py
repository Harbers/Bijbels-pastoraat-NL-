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
  /api/psalm:
    get:
      summary: Haal exact één vers op
      operationId: getPsalmVers
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
  /api/psalm/max:
    get:
      summary: Max vers
      operationId: getPsalmMax
      parameters:
        - in: query
          name: psalm
          required: true
          schema: { type: integer, minimum: 1, maximum: 150 }
      responses:
        "200": { description: Succes }
"""
@app.get("/openapi.yaml", include_in_schema=False)
def openapi_yaml():
    return Response(content=OPENAPI_YAML, media_type="application/yaml")

@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
def manifest():
    return JSONResponse({
        "schema_version": "v1",
        "name_for_human": "Bijbels-Pastoraat-NL",
        "name_for_model": "BijbelsPastoraatNL",
        "description_for_human": "Haal psalmverzen op uit de officiële berijming van 1773.",
        "description_for_model": "Gebruik getPsalmMax en getPsalmVers; bron psalmboek.nl (1773).",
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

@app.get("/api/psalm", response_model=PsalmVersResponse)
def get_psalm_vers(psalm: int = Query(..., ge=1, le=150), vers: int = Query(..., ge=1)):
    try:
        max_vers = client.get_max_vers(psalm)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Fout bij ophalen bron: {e}")

    if vers > max_vers:
        raise HTTPException(status_code=400, detail=f"Versnummer valt buiten bereik [1,{max_vers}] voor psalm {psalm}.")

    try:
        text = client.get_vers(psalm, vers)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Fout bij ophalen bron: {e}")

    return PsalmVersResponse(
        psalm=psalm,
        vers=vers,
        text=text,
        bron=f"{settings.PSALM_SOURCE_BASE}/psalmen.php?berijming={client.berijming}&psalm={psalm}#{vers}",
    )
