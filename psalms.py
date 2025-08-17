from fastapi import APIRouter, HTTPException, Query
from .main import client  # de PsalmboekClient instantie
from typing import Optional

router = APIRouter(prefix="/api/psalm", tags=["psalmen"])


@router.get("/max")
def get_max_vers(
    psalm: int = Query(..., description="Psalmnummer (1–150)")
) -> dict:
    """
    Bepaal het maximale versnummer van een psalm.
    """
    try:
        max_vers = client.get_max_vers(psalm)
        if max_vers < 1:
            raise HTTPException(status_code=404, detail=f"Geen verzen gevonden voor Psalm {psalm}.")
        return {"psalm": psalm, "max_vers": max_vers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fout bij ophalen: {e}")


@router.get("/vers")
def get_psalm_vers(
    psalm: int = Query(..., description="Psalmnummer (1–150)"),
    vers: int = Query(..., description="Versnummer (>=1)")
) -> dict:
    """
    Haal een specifiek vers op van een psalm.
    """
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
