cat >/opt/bijbels-pastoraat/app/config.py <<'EOF'
from pydantic import BaseSettings, AnyHttpUrl


class Settings(BaseSettings):
    # Bronwebsite (huidige PHP-structuur van psalmboek.nl)
    PSALM_SOURCE_BASE: AnyHttpUrl = "https://psalmboek.nl"
    PSALM_BERIJMING: str = "1773"
    CACHE_SECONDS: int = 600  # simpele in-memory cache

    class Config:
        env_file = ".env"


settings = Settings()
EOF
