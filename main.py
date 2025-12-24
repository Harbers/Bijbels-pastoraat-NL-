from __future__ import annotations

from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from config import settings
from psalm_parser import ParsedPsalmReference, parse_psalm_reference
from psalms import client
from response_validation import ensure_response_matches_schema
from schemas import PsalmMaxResponse, PsalmVersResponse


app = FastAPI(
    title="Bijbels-Pastoraat-NL Backend",
    version="1.0.0",
    description="API voor berijmde psalmverzen (1773) via psalmboek.nl",
    contact={"name": "Bijbels-Pastoraat-NL", "email": "support@bijbels-pastoraat-nl.onrender.com"},
    license_info={"name": "MIT"},
)

# CORS: Caddy handelt OPTIONS al af, maar dit helpt bij directe calls naar de backend.
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
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/healthz", include_in_schema=False)
def healthz() -> Dict[str, str]:
    return {"status": "ok"}


def _schema_response(payload: Dict[str, Any], *, status_code: int = 200) -> JSONResponse:
    """
    Valideert payload tegen het response-schema voor psalm_lookup_1773.
    Als validatie faalt: geef een duidelijke 500 met detail (zodat je het kunt fixen).
    """
    try:
        ensure_response_matches_schema(payload)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f"Schema-validatie faalde: {exc}")
    return JSONResponse(content=payload, status_code=status_code)


OPENAPI_YAML = """openapi: 3.1.0
info:
  title: Bijbels-Pastoraat-NL Backend
  version: "1.0.0"
  description: |
    API voor berijmde psalmverzen (1773) via psalmboek.nl
    Endpoints:
      - GET /api/psalm/vers?psalm={1..150}&vers={1..}
      - GET /api/psalm/max?psalm={1..150}
      - GET /api/psalm/lookup?query=<psalmverzoek>
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
  /api/psalm/lookup:
    get:
      summary: Normaliseer psalmverzoek (berijming 1773) en haal verzen op
      operationId: psalm_lookup_1773
      parameters:
        - in: query
          name: query
          required: true
          schema: { type: string, minLength: 1 }
      responses:
        "200": { description: Schema-conform resultaat }
        "404": { description: Vers niet gevonden in bron }
        "502": { description: Fout bij bron of verificatie }
"""


@app.get("/openapi.yaml", include_in_schema=False)
def openapi_yaml() -> Response:
    return Response(content=OPENAPI_YAML, media_type="application/yaml")


@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
def manifest() -> JSONResponse:
    return JSONResponse(
        {
            "schema_version": "v1",
            "name_for_human": "Bijbels-Pastoraat-NL",
            "name_for_model": "bijbels_pastoraat",
            "description_for_human": "Haal psalmverzen op uit de officiële berijming van 1773.",
            "description_for_model": (
                "Bijbelse pastorale zorg (gereformeerd, Christus-centraal). "
                "Voor berijmde psalmen (1773) gebruik altijd de plugin bijbels_pastoraat.get_berijmd_psalmvers "
                "(GET /api/psalm/vers). "
                "Bij meerdere verzen: normaliseer via /api/psalm/lookup?query=... "
                "Bij plugin-fout: 'Vers <x> van Psalm <y> kon niet worden opgehaald.'"
            ),
            "auth": {"type": "none"},
            "api": {
                "type": "openapi",
                "url": "https://gpt-harbers.duckdns.org/openapi.yaml",
                "is_user_authenticated": False,
            },
            "logo_url": "https://gpt-harbers.duckdns.org/static/logo.svg",
            "contact_email": "support@bijbels-pastoraat-nl.onrender.com",
            "legal_info_url": "https://gpt-harbers.duckdns.org/legal",
        }
    )


SVG_LOGO = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256">
  <rect width="256" height="256" fill="#f2f2f2"/>
  <text x="50%" y="50%" dy="8" text-anchor="middle" font-family="Georgia" font-size="28">1773</text>
</svg>
"""


@app.get("/static/logo.svg", include_in_schema=False)
def logo_svg() -> Response:
    return Response(content=SVG_LOGO, media_type="image/svg+xml")


@app.get("/legal", include_in_schema=False, response_class=HTMLResponse)
def legal() -> str:
    return "<h1>Privacybeleid</h1><p>Geen persoonsgegevens worden opgeslagen.</p>"


# --- API ---------------------------------------------------------------------


@app.get("/api/psalm/lookup")
def psalm_lookup(query: str = Query(..., min_length=1)) -> JSONResponse:
    """
    Ondersteunt invoer zoals:
    - 'Psalm 118: 1, 2 en 5'
    - 'ps 118:1-3,5'
    - 'Ps. 23 vers 1 t/m 3 en 6'
    """
    try:
        parsed: ParsedPsalmReference = parse_psalm_reference(query)
    except Exception as exc:
        payload = {
            "intent": "psalm_lookup_1773",
            "status": "invalid_request",
            "request": {"raw": query},
            "result": {"message": f"Ongeldig verzoek: {exc}"},
        }
        return _schema_response(payload, status_code=400)

    if parsed.status != "ok":
        # parser levert zelf schema-conforme foutstructuur via to_dict()
        return _schema_response(parsed.to_dict(), status_code=400)

    psalm_number = int(parsed.request["psalm_number"])
    verses: List[int] = list(parsed.request["verses"])

    try:
        max_vers = client.get_max_vers(psalm_number)
    except Exception as exc:
        payload = {
            "intent": "psalm_lookup_1773",
            "status": "verification_failed",
            "request": parsed.request,
            "result": {"message": f"Fout bij bron: {exc}"},
        }
        return _schema_response(payload, status_code=502)

    out_of_range = [v for v in verses if v > max_vers]
    if out_of_range:
        payload = {
            "intent": "psalm_lookup_1773",
            "status": "not_found",
            "request": parsed.request,
            "result": {"message": f"Vers {out_of_range[0]} van Psalm {psalm_number} kon niet worden opgehaald."},
        }
        return _schema_response(payload, status_code=404)

    verse_payloads: List[Dict[str, Any]] = []
    try:
        for verse in verses:
            text = client.get_vers(psalm_number, verse)
            verse_payloads.append({"verse": verse, "text": text})
    except ValueError:
        payload = {
            "intent": "psalm_lookup_1773",
            "status": "not_found",
            "request": parsed.request,
            "result": {"message": f"Vers {verse} van Psalm {psalm_number} kon niet worden opgehaald."},
        }
        return _schema_response(payload, status_code=404)
    except Exception as exc:
        payload = {
            "intent": "psalm_lookup_1773",
            "status": "verification_failed",
            "request": parsed.request,
            "result": {"message": f"Fout bij bron: {exc}"},
        }
        return _schema_response(payload, status_code=502)

    payload = {
        "intent": "psalm_lookup_1773",
        "status": "ok",
        "request": parsed.request,
        "result": {"verified": True, "verses": verse_payloads},
    }
    return _schema_response(payload)


@app.get("/api/psalm/max", response_model=PsalmMaxResponse)
def get_psalm_max(psalm: int = Query(..., ge=1, le=150)) -> PsalmMaxResponse:
    try:
        max_vers = client.get_max_vers(psalm)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Fout bij ophalen bron: {exc}") from exc

    return PsalmMaxResponse(
        psalm=psalm,
        max_vers=max_vers,
        bron=f"{settings.PSALM_SOURCE_BASE}/psalmen.php?berijming={client.berijming}&psalm={psalm}",
    )


@app.get("/api/psalm/vers", response_model=PsalmVersResponse)
def get_psalm_vers(psalm: int = Query(..., ge=1, le=150), vers: int = Query(..., ge=1)) -> PsalmVersResponse:
    try:
        max_vers = client.get_max_vers(psalm)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Fout bij ophalen bron: {exc}") from exc

    if vers > max_vers:
        raise HTTPException(status_code=400, detail=f"Vers {vers} van Psalm {psalm} kon niet worden opgehaald.")

    try:
        text = client.get_vers(psalm, vers)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Vers {vers} van Psalm {psalm} kon niet worden opgehaald.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Fout bij ophalen bron: {exc}") from exc

    return PsalmVersResponse(
        psalm=psalm,
        vers=vers,
        text=text,
        bron=f"{settings.PSALM_SOURCE_BASE}/psalmen.php?berijming={client.berijming}&psalm={psalm}#{vers}",
    )
