from fastapi import FastAPI
from .psalms import router as psalms_router  # importeer de psalms-router

# Maak de FastAPI-app aan
app = FastAPI(
    title="Bijbels-Pastoraat-NL Backend",
    version="1.0.0",
    description="Backend API voor psalmteksten (berijming 1773)."
)

# Basis healthcheck, handig voor uptime-monitoring
@app.get("/healthz", include_in_schema=False)
def root_healthz():
    return {"status": "ok"}

# Mount de psalms-router zodat de endpoints actief worden
app.include_router(psalms_router)
