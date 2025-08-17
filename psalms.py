cat >/opt/bijbels-pastoraat/app/psalms.py <<'EOF'
from fastapi import APIRouter, HTTPException, Query
from .psalm_client import client

router = APIRouter(prefix="/api/psalm", tags=["psalmen"])


@router.get("/healthz", include_in_schema=False)
def healthcheck() -> dict:
    return {"status": "ok"}


@router.get("/max")
def get_max_vers(psalm: int = Query(..., ge=1, le=150, description="Psalmnummer (1–150)")) -> dict:
    try:
        max_vers = client.get_max_vers(psalm)
        if max_vers < 1:
            raise HTTPException(status_code=404, detail=f"Geen verzen gevonden voor Psalm {psalm}.")
        return {"psalm": psalm, "max_vers": max_vers}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fout bij ophalen: {e}")


@router.get("/vers")
def get_psalm_vers(
    psalm: int = Query(..., ge=1, le=150, description="Psalmnummer (1–150)"),
    vers: int = Query(..., ge=1, description="Versnummer (>=1)"),
) -> dict:
    try:
        max_vers = client.get_max_vers(psalm)
        if vers > max_vers:
            raise HTTPException(
                status_code=404,
                detail=f"Psalm {psalm} heeft maar {max_vers} verzen, niet {vers}.",
            )
        tekst = client.get_vers(psalm, vers)
        return {"psalm": psalm, "vers": vers, "tekst": tekst}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fout bij ophalen: {e}")


EOF
