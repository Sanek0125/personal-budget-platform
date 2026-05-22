from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, Index, UniqueConstraint, inspect

from app.api.budgets import (
    create_budget,
    create_budget_limit,
    get_budget_progress,
    list_budgets,
)
from app.db.base import Base
from app.models import Budget, BudgetLimit, Category, Transaction, TransactionSplit
from app.schemas.budget import BudgetCreate, BudgetLimitCreate
from app.services.budgets import calculate_budget_progress


class _ScalarResult:
    def __init__(
        self, value: object | None = None, values: list[object] | None = None
    ) -> None:
        self._value = value
        self._values = values or ([] if value is None else [value])

    def scalar_one_or_none(self) -> object | None:
        return self._value

    def scalars(self) -> "_ScalarResult":
        return self

    def all(self) -> list[object]:
        return self._values

    def unique(self) -> "_ScalarResult":
        return self


class _FakeAsyncSession:
    def __init__(self, *results: object | list[object] | None) -> None:
        self.results = list(results)
        self.added: list[object] = []
        self.committed = False
        self.rolled_back = False
        self.refreshed: list[object] = []
        self.statements: list[object] = []

    async def execute(self, statement: object) -> _ScalarResult:
        self.statements.append(statement)
        value = self.results.pop(0) if self.results else None
        if isinstance(value, list):
            return _ScalarResult(values=value)
        return _ScalarResult(value)

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def refresh(
        self, obj: object, attribute_names: list[str] | None = None
    ) -> None:
        del attribute_names
        self.refreshed.append(obj)


def _category(workspace_id, category_id=None, type="expense") -> Category:
    return Category(
        id=category_id or uuid4(),
        workspace_id=workspace_id,
        name="Food",
        type=type,
    )


def _budget(workspace_id, budget_id=None, currency_code="USD") -> Budget:
    return Budget(
        id=budget_id or uuid4(),
        workspace_id=workspace_id,
        name="May budget",
        period_type="monthly",
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 31),
        currency_code=currency_code,
        is_active=True,
    )


def _limit(budget_id, category_id, amount="100") -> BudgetLimit:
    return BudgetLimit(
        id=uuid4(),
        budget_id=budget_id,
        category_id=category_id,
        amount=Decimal(amount),
        currency_code="USD",
        rollover=False,
    )


def _transaction(
    workspace_id,
    category_id,
    amount="-25",
    currency_code="USD",
    base_amount=None,
    base_currency_code=None,
) -> Transaction:
    return Transaction(
        id=uuid4(),
        workspace_id=workspace_id,
        account_id=uuid4(),
        type="expense",
        status="posted",
        occurred_at=datetime(2026, 5, 12, tzinfo=UTC),
        amount=Decimal(amount),
        currency_code=currency_code,
        base_amount=Decimal(base_amount) if base_amount is not None else None,
        base_currency_code=base_currency_code,
        description="Groceries",
        category_id=category_id,
        source="manual",
        fingerprint=str(uuid4()),
    )


def test_budget_models_are_registered_with_metadata() -> None:
    assert Budget.__tablename__ == "budgets"
    assert BudgetLimit.__tablename__ == "budget_limits"
    assert {"budgets", "budget_limits"}.issubset(Base.metadata.tables)


def test_budget_model_has_expected_constraints_and_indexes() -> None:
    budget_table = Base.metadata.tables["budgets"]
    limit_table = Base.metadata.tables["budget_limits"]
    budget_checks = {
        constraint.name
        for constraint in budget_table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    limit_checks = {
        constraint.name
        for constraint in limit_table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    unique_constraints = {
        constraint.name
        for constraint in limit_table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    indexes = {
        index.name
        for index in budget_table.indexes | limit_table.indexes
        if isinstance(index, Index)
    }

    assert "ck_budgets_period_type" in budget_checks
    assert "ck_budgets_period_dates" in budget_checks
    assert "ck_budget_limits_amount_positive" in limit_checks
    assert "uq_budget_limits_budget_category" in unique_constraints
    assert {
        "ix_budgets_workspace_period",
        "ix_budget_limits_budget_id",
        "ix_budget_limits_category_id",
    }.issubset(indexes)


def test_budget_relationship_annotations_are_configured() -> None:
    budget_relationships = {rel.key for rel in inspect(Budget).relationships}
    limit_relationships = {rel.key for rel in inspect(BudgetLimit).relationships}

    assert {"workspace", "currency", "limits"}.issubset(budget_relationships)
    assert {"budget", "category", "currency"}.issubset(limit_relationships)


def test_budget_schema_normalizes_currency_and_requires_month_dates() -> None:
    payload = BudgetCreate(
        name="May budget",
        period_type="monthly",
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 31),
        currency_code="usd",
    )

    assert payload.currency_code == "USD"


def test_budget_schema_rejects_non_monthly_period() -> None:
    try:
        BudgetCreate(
            name="Bad budget",
            period_type="weekly",
            period_start=date(2026, 5, 1),
            period_end=date(2026, 5, 31),
            currency_code="USD",
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("budget period_type must be monthly")


def test_budget_limit_schema_rejects_non_positive_amount() -> None:
    try:
        BudgetLimitCreate(category_id=uuid4(), amount=Decimal("0"), currency_code="USD")
    except ValidationError:
        pass
    else:
        raise AssertionError("budget limit amount must be positive")


def test_calculate_budget_progress_counts_monthly_category_expenses() -> None:
    workspace_id = uuid4()
    category_id = uuid4()
    budget = _budget(workspace_id)
    limit = _limit(budget.id, category_id, "100")
    transaction = _transaction(workspace_id, category_id, "-25")

    progress = calculate_budget_progress(budget, [limit], [transaction])

    assert progress.total_limit == Decimal("100")
    assert progress.total_spent == Decimal("25")
    assert progress.total_remaining == Decimal("75")
    assert progress.limits[0].spent_amount == Decimal("25")
    assert progress.limits[0].remaining_amount == Decimal("75")
    assert progress.limits[0].percent_used == Decimal("25.00")


def test_calculate_budget_progress_counts_split_category_amounts() -> None:
    workspace_id = uuid4()
    food_id = uuid4()
    transport_id = uuid4()
    budget = _budget(workspace_id)
    food_limit = _limit(budget.id, food_id, "100")
    transaction = _transaction(workspace_id, None, "-30")
    transaction.splits = [
        TransactionSplit(
            category_id=food_id, amount=Decimal("-10"), currency_code="USD"
        ),
        TransactionSplit(
            category_id=transport_id, amount=Decimal("-20"), currency_code="USD"
        ),
    ]

    progress = calculate_budget_progress(budget, [food_limit], [transaction])

    assert progress.total_spent == Decimal("10")
    assert progress.limits[0].spent_amount == Decimal("10")


def test_calculate_budget_progress_uses_base_amount_for_budget_currency() -> None:
    workspace_id = uuid4()
    category_id = uuid4()
    budget = _budget(workspace_id, currency_code="USD")
    limit = _limit(budget.id, category_id, "100")
    transaction = _transaction(
        workspace_id,
        category_id,
        amount="-1000",
        currency_code="RUB",
        base_amount="-10",
        base_currency_code="USD",
    )

    progress = calculate_budget_progress(budget, [limit], [transaction])

    assert progress.total_spent == Decimal("10")
    assert progress.limits[0].spent_amount == Decimal("10")


def test_calculate_budget_progress_ignores_non_expense_negative_transactions() -> None:
    workspace_id = uuid4()
    category_id = uuid4()
    budget = _budget(workspace_id)
    limit = _limit(budget.id, category_id, "100")
    adjustment = _transaction(workspace_id, category_id, "-25")
    adjustment.type = "adjustment"
    transfer = _transaction(workspace_id, category_id, "-30")
    transfer.type = "transfer"

    progress = calculate_budget_progress(budget, [limit], [adjustment, transfer])

    assert progress.total_spent == Decimal("0")
    assert progress.limits[0].spent_amount == Decimal("0")


async def test_list_budgets_returns_workspace_budgets() -> None:
    workspace_id = uuid4()
    budgets = [_budget(workspace_id)]
    session = _FakeAsyncSession(budgets)

    result = await list_budgets(workspace_id, session)

    assert result == budgets


async def test_create_budget_persists_budget() -> None:
    workspace_id = uuid4()
    payload = BudgetCreate(
        name="May budget",
        period_type="monthly",
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 31),
        currency_code="USD",
    )
    session = _FakeAsyncSession(workspace_id)

    result = await create_budget(workspace_id, payload, session)

    assert isinstance(result, Budget)
    assert result.workspace_id == workspace_id
    assert result.currency_code == "USD"
    assert session.added == [result]
    assert session.committed is True
    assert session.refreshed == [result]


async def test_create_budget_limit_requires_category_in_budget_workspace() -> None:
    workspace_id = uuid4()
    budget = _budget(workspace_id)
    payload = BudgetLimitCreate(
        category_id=uuid4(),
        amount=Decimal("100"),
        currency_code="USD",
    )
    session = _FakeAsyncSession(budget, None)

    try:
        await create_budget_limit(budget.id, payload, session)
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Category not found in this workspace"
    else:
        raise AssertionError("missing category should fail")


async def test_create_budget_limit_persists_limit() -> None:
    workspace_id = uuid4()
    category_id = uuid4()
    budget = _budget(workspace_id)
    category = _category(workspace_id, category_id)
    payload = BudgetLimitCreate(
        category_id=category_id,
        amount=Decimal("100"),
        currency_code="USD",
    )
    session = _FakeAsyncSession(budget, category)

    result = await create_budget_limit(budget.id, payload, session)

    assert isinstance(result, BudgetLimit)
    assert result.budget_id == budget.id
    assert result.category_id == category_id
    assert session.added == [result]
    assert session.committed is True


async def test_get_budget_progress_returns_progress_for_budget() -> None:
    workspace_id = uuid4()
    category_id = uuid4()
    budget = _budget(workspace_id)
    limit = _limit(budget.id, category_id, "100")
    budget.limits = [limit]
    transaction = _transaction(workspace_id, category_id, "-25")
    session = _FakeAsyncSession(budget, [transaction])

    result = await get_budget_progress(budget.id, session)

    assert result.budget_id == budget.id
    assert result.total_spent == Decimal("25")
    assert result.limits[0].category_id == category_id
