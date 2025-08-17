from pydantic import BaseModel, Field, HttpUrl


class PsalmVersResponse(BaseModel):
    psalm: int = Field(..., ge=1, le=150, description="Psalmnummer 1..150")
    vers: int = Field(..., ge=1, description="Versnummer (1..max)")
    text: str = Field(..., description="Exacte berijmde tekstregel van psalmboek.nl (1773)")
    bron: HttpUrl


class PsalmMaxResponse(BaseModel):
    psalm: int = Field(..., ge=1, le=150)
    max_vers: int = Field(..., ge=1)
    bron: HttpUrl
