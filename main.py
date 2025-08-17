cat >/opt/bijbels-pastoraat/app/main.py <<'EOF'
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .psalms import router as psalms_router

app = FastAPI(
    title="Bijbels-Pastoraat-NL Backend",
    version="1.0.0",
    description="Backend API voor psalmteksten (berijming 1773)",
)

ALLOWED_ORIGINS = [
    "https://chat.openai.com",
    "https://gpt-harbers.duckdns.org",
    "http://91.99.2.139:8000",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz", include_in_schema=False)
def root_healthz():
    return {"status": "ok"}

# monteer de psalm-router
app.include_router(psalms_router)
EOF
