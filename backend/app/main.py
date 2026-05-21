from fastapi import FastAPI

from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Return a minimal service health status."""
    return {"status": "ok", "service": "personal-budget-backend"}
