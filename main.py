from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .psalms import router as psalms_router

app = FastAPI(
    title="Bijbels-Pastoraat-NL Backend",
    version="1.0.0",
    description="Backend API voor psalmteksten (berijming 1773).",
)

# CORS – sta ChatGPT en uw eigen origin toe. Voeg test-origins toe zolang u ontwikkelt.
ALLOWED_ORIGINS = [
    "https://chat.openai.com",
    "https://gpt-harbers.duckdns.org",
    "http://91.99.2.139:8000",   # lokaal testen via IP
    "http://localhost:8000",     # eventueel lokale tests
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root healthcheck (handig voor load balancers / Caddy)
@app.get("/healthz", include_in_schema=False)
def root_healthz():
    return {"status": "ok"}

# Mount de psalm-endpoints
app.include_router(psalms_router)
