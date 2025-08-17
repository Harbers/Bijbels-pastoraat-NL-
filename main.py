from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse
from .schemas import PsalmVersResponse, PsalmMaxResponse
from .psalms import client
from .config import settings
from pathlib import Path

app = FastAPI(
    title="Bijbels-Pastoraat-NL Backend",
    version="1.0.0",
    description="API voor berijmde psalmverzen (1773) via psalmboek.nl",
    contact={"name": "Bijbels-Pastoraat-NL", "email": "support@bijbels-pastoraat-nl.onrender.com"},
    license_info={"name": "MIT"},
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/healthz", summary="Health check", include_in_schema=False)
def healthz():
    return {"status": "ok"}


# Static logo
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

@app.get("/static/logo.svg", include_in_schema=False)
def get_logo():
    file_path = STATIC_DIR / "logo.svg"
    if not file_path.exists():
        return JSONResponse({"error": "logo missing"}, status_code=404)
    return FileResponse(file_path, media_type="image/svg+xml")


@app.get(
    "/api/psalm/max",
    response_model=PsalmMaxResponse,
    summary="Bepaal het maximaal beschikbare versnummer voor een psalm (berijming 1773)",
)
def get_psalm_max(
    psalm: int = Query(..., ge=1, le=150, description="Psalmnummer 1..150")
):
    try:
        max_vers = client.get_max_vers(psalm)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Fout bij ophalen bron: {e}")

    return PsalmMaxResponse(
        psalm=psalm,
        max_vers=max_vers,
        bron=f"{settings.PSALM_SOURCE_BASE}/berijming/{client.berijming}/psalm/{psalm}",
    )


@app.get(
    "/api/psalm",
    response_model=PsalmVersResponse,
    summary="Haal exact één vers op uit berijming 1773 (psalmboek.nl)",
)
def get_psalm_vers(
    psalm: int = Query(..., ge=1, le=150),
    vers: int = Query(..., ge=1),
):
    # Range-controle tegen max
    try:
        max_vers = client.get_max_vers(psalm)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Fout bij ophalen bron: {e}")

    if vers > max_vers:
        raise HTTPException(
            status_code=400,
            detail=f"Versnummer valt buiten bereik [1,{max_vers}] voor psalm {psalm}.",
        )

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
        bron=f"{settings.PSALM_SOURCE_BASE}/berijming/{client.berijming}/psalm/{psalm}/{vers}",
    )
