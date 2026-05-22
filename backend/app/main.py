from fastapi import FastAPI

from app.api.accounts import router as accounts_router
from app.api.budgets import router as budgets_router
from app.api.categories import router as categories_router
from app.api.category_rules import router as category_rules_router
from app.api.debts import router as debts_router
from app.api.imports import router as imports_router
from app.api.rewards import router as rewards_router
from app.api.transactions import router as transactions_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)
app.include_router(accounts_router)
app.include_router(budgets_router)
app.include_router(categories_router)
app.include_router(category_rules_router)
app.include_router(debts_router)
app.include_router(imports_router)
app.include_router(rewards_router)
app.include_router(transactions_router)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Return a minimal service health status."""
    return {"status": "ok", "service": "personal-budget-backend"}
