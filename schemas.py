from pydantic import BaseModel, Field, HttpUrl


class PsalmVersResponse(BaseModel):
    psalm: int = Field(..., ge=1, le=150)
    vers: int = Field(..., ge=1)
    text: str
    bron: HttpUrl


class PsalmMaxResponse(BaseModel):
    psalm: int = Field(..., ge=1, le=150)
    max_vers: int = Field(..., ge=1)
    bron: HttpUrl
