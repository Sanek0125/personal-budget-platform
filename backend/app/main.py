from fastapi import FastAPI

from app.api.accounts import router as accounts_router
from app.api.categories import router as categories_router
from app.api.imports import router as imports_router
from app.api.transactions import router as transactions_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)
app.include_router(accounts_router)
app.include_router(categories_router)
app.include_router(imports_router)
app.include_router(transactions_router)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Return a minimal service health status."""
    return {"status": "ok", "service": "personal-budget-backend"}
