from pydantic import BaseSettings, AnyHttpUrl

class Settings(BaseSettings):
    PSALM_SOURCE_BASE: AnyHttpUrl = "https://psalmboek.nl"
    PSALM_BERIJMING: str = "1773"
    CACHE_SECONDS: int = 600

    class Config:
        env_file = ".env"

settings = Settings()
