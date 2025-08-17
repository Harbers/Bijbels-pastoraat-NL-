from pydantic import BaseSettings, AnyHttpUrl


class Settings(BaseSettings):
    # Pas dit IP/poort aan als u een domein gebruikt.
    SERVER_BASE: AnyHttpUrl = "http://91.99.2.139:8000"
    # Toegestane origins voor CORS (voeg uw frontend/domeinen toe indien nodig)
    CORS_ORIGINS: list[str] = [
        "https://chat.openai.com",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    # Scrape-bron – behoud psalmboek.nl (berijming 1773)
    PSALM_SOURCE_BASE: AnyHttpUrl = "https://psalmboek.nl"
    PSALM_BERIJMING: str = "1773"
    # Simpele cache-tijd in seconden (0 = uit)
    CACHE_SECONDS: int = 3600

    class Config:
        env_prefix = "BP_"
        case_sensitive = False


settings = Settings()
