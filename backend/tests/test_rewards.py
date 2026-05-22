from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, Index, inspect

from app.api.rewards import (
    calculate_expected_reward,
    create_cashback_rule,
    create_reward_event,
    create_reward_program,
    list_reward_events,
    list_reward_programs,
)
from app.db.base import Base
from app.models import CashbackRule, Category, RewardEvent, RewardProgram, Transaction
from app.schemas.reward import (
    CashbackRuleCreate,
    ExpectedRewardRequest,
    RewardEventCreate,
    RewardProgramCreate,
)
from app.services.rewards import calculate_reward_for_transaction


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


def _program(
    workspace_id, program_id=None, program_type="cashback", currency_code="USD"
) -> RewardProgram:
    return RewardProgram(
        id=program_id or uuid4(),
        workspace_id=workspace_id,
        name="Main rewards",
        program_type=program_type,
        currency_code=currency_code,
        issuer_name="Bank",
        is_active=True,
    )


def _category(workspace_id, category_id=None) -> Category:
    return Category(
        id=category_id or uuid4(),
        workspace_id=workspace_id,
        name="Groceries",
        type="expense",
    )


def _transaction(
    workspace_id, category_id=None, amount="-100", currency_code="USD"
) -> Transaction:
    return Transaction(
        id=uuid4(),
        workspace_id=workspace_id,
        account_id=uuid4(),
        type="expense",
        status="posted",
        occurred_at=datetime(2026, 5, 20, tzinfo=UTC),
        amount=Decimal(amount),
        currency_code=currency_code,
        description="Grocery store",
        merchant_name="SuperMart",
        category_id=category_id,
        source="manual",
        fingerprint=str(uuid4()),
    )


def _rule(
    workspace_id, program_id, category_id=None, rate="0.02", priority=100
) -> CashbackRule:
    return CashbackRule(
        id=uuid4(),
        workspace_id=workspace_id,
        program_id=program_id,
        name="2 percent",
        rate=Decimal(rate),
        spend_currency_code="USD",
        category_id=category_id,
        merchant_pattern=None,
        min_spend_amount=None,
        max_reward_amount=None,
        priority=priority,
        is_active=True,
    )


def test_reward_models_are_registered_with_metadata() -> None:
    assert RewardProgram.__tablename__ == "reward_programs"
    assert RewardEvent.__tablename__ == "reward_events"
    assert CashbackRule.__tablename__ == "cashback_rules"
    assert {"reward_programs", "reward_events", "cashback_rules"}.issubset(
        Base.metadata.tables
    )


def test_reward_models_have_expected_constraints_and_indexes() -> None:
    program_table = Base.metadata.tables["reward_programs"]
    event_table = Base.metadata.tables["reward_events"]
    rule_table = Base.metadata.tables["cashback_rules"]
    checks = {
        constraint.name
        for table in (program_table, event_table, rule_table)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    indexes = {
        index.name
        for table in (program_table, event_table, rule_table)
        for index in table.indexes
        if isinstance(index, Index)
    }

    assert "ck_reward_programs_type" in checks
    assert "ck_reward_programs_currency_consistency" in checks
    assert "ck_reward_events_type" in checks
    assert "ck_reward_events_status" in checks
    assert "ck_reward_events_amount_positive" in checks
    assert "ck_cashback_rules_rate_positive" in checks
    assert {
        "ix_reward_programs_workspace_id",
        "ix_reward_events_workspace_occurred_at",
        "ix_cashback_rules_workspace_program",
    }.issubset(indexes)


def test_reward_relationship_annotations_are_configured() -> None:
    program_relationships = {rel.key for rel in inspect(RewardProgram).relationships}
    event_relationships = {rel.key for rel in inspect(RewardEvent).relationships}
    rule_relationships = {rel.key for rel in inspect(CashbackRule).relationships}

    assert {"workspace", "currency", "events", "cashback_rules"}.issubset(
        program_relationships
    )
    assert {
        "workspace",
        "program",
        "source_transaction",
        "reward_transaction",
        "cashback_rule",
        "currency",
    }.issubset(event_relationships)
    assert {"workspace", "program", "category", "spend_currency"}.issubset(
        rule_relationships
    )


def test_reward_program_schema_enforces_currency_rules() -> None:
    payload = RewardProgramCreate(
        name="Cash", program_type="cashback", currency_code="usd"
    )
    assert payload.currency_code == "USD"

    try:
        RewardProgramCreate(name="Points", program_type="points", currency_code="USD")
    except ValidationError:
        pass
    else:
        raise AssertionError("points program must not accept currency_code")


def test_reward_event_schema_requires_positive_amount_and_money_currency() -> None:
    try:
        RewardEventCreate(
            program_id=uuid4(),
            event_type="earned",
            amount=Decimal("0"),
            occurred_at=datetime.now(UTC),
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("reward event amount must be positive")

    try:
        RewardEventCreate(
            program_id=uuid4(),
            event_type="earned",
            amount=Decimal("1"),
            occurred_at=datetime.now(UTC),
            reward_kind="cashback",
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("money cashback event must require currency")


def test_cashback_rule_schema_normalizes_currency_and_requires_positive_rate() -> None:
    payload = CashbackRuleCreate(
        program_id=uuid4(), name="2%", rate=Decimal("0.02"), spend_currency_code="usd"
    )
    assert payload.spend_currency_code == "USD"

    try:
        CashbackRuleCreate(
            program_id=uuid4(), name="bad", rate=Decimal("0"), spend_currency_code="USD"
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("cashback rule rate must be positive")


def test_calculate_reward_for_money_cashback() -> None:
    workspace_id = uuid4()
    category_id = uuid4()
    program = _program(workspace_id, program_type="cashback", currency_code="USD")
    tx = _transaction(workspace_id, category_id, "-100")
    rule = _rule(workspace_id, program.id, category_id, "0.02")

    result = calculate_reward_for_transaction(program, tx, [rule])

    assert result is not None
    assert result.amount == Decimal("2.000000")
    assert result.currency_code == "USD"
    assert result.rule_id == rule.id


def test_calculate_reward_for_points_and_caps() -> None:
    workspace_id = uuid4()
    program = _program(workspace_id, program_type="points", currency_code=None)
    tx = _transaction(workspace_id, amount="-1000")
    rule = _rule(workspace_id, program.id, rate="1.5")
    rule.max_reward_amount = Decimal("1000")

    result = calculate_reward_for_transaction(program, tx, [rule])

    assert result is not None
    assert result.amount == Decimal("1000.000000")
    assert result.currency_code is None


def test_calculate_reward_chooses_lowest_priority_matching_rule() -> None:
    workspace_id = uuid4()
    program = _program(workspace_id)
    tx = _transaction(workspace_id, amount="-100")
    low = _rule(workspace_id, program.id, rate="0.01", priority=200)
    high = _rule(workspace_id, program.id, rate="0.05", priority=10)

    result = calculate_reward_for_transaction(program, tx, [low, high])

    assert result is not None
    assert result.rule_id == high.id
    assert result.amount == Decimal("5.000000")


def test_calculate_reward_ignores_income_deleted_and_currency_mismatch() -> None:
    workspace_id = uuid4()
    program = _program(workspace_id)
    rule = _rule(workspace_id, program.id)
    income = _transaction(workspace_id, amount="100")
    income.type = "income"
    deleted = _transaction(workspace_id, amount="-100")
    deleted.status = "deleted"
    mismatch = _transaction(workspace_id, amount="-100", currency_code="EUR")

    assert calculate_reward_for_transaction(program, income, [rule]) is None
    assert calculate_reward_for_transaction(program, deleted, [rule]) is None
    assert calculate_reward_for_transaction(program, mismatch, [rule]) is None


async def test_list_reward_programs_returns_workspace_programs() -> None:
    workspace_id = uuid4()
    programs = [_program(workspace_id)]
    session = _FakeAsyncSession(programs)

    result = await list_reward_programs(workspace_id, session)

    assert result == programs


async def test_create_reward_program_persists_program() -> None:
    workspace_id = uuid4()
    payload = RewardProgramCreate(
        name="Cashback", program_type="cashback", currency_code="USD"
    )
    session = _FakeAsyncSession(workspace_id)

    result = await create_reward_program(workspace_id, payload, session)

    assert isinstance(result, RewardProgram)
    assert result.workspace_id == workspace_id
    assert result.currency_code == "USD"
    assert session.added == [result]
    assert session.committed is True


async def test_create_cashback_rule_requires_program_in_workspace() -> None:
    workspace_id = uuid4()
    payload = CashbackRuleCreate(
        program_id=uuid4(), name="2%", rate=Decimal("0.02"), spend_currency_code="USD"
    )
    session = _FakeAsyncSession(None)

    try:
        await create_cashback_rule(workspace_id, payload, session)
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Reward program not found in this workspace"
    else:
        raise AssertionError("missing program should fail")


async def test_create_cashback_rule_rejects_category_outside_workspace() -> None:
    workspace_id = uuid4()
    program = _program(workspace_id)
    payload = CashbackRuleCreate(
        program_id=program.id,
        name="2%",
        rate=Decimal("0.02"),
        spend_currency_code="USD",
        category_id=uuid4(),
    )
    session = _FakeAsyncSession(program, None)

    try:
        await create_cashback_rule(workspace_id, payload, session)
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Category not found in this workspace"
    else:
        raise AssertionError("foreign category should fail")


async def test_create_reward_event_rejects_cashback_rule_outside_program() -> None:
    workspace_id = uuid4()
    program = _program(workspace_id)
    payload = RewardEventCreate(
        program_id=program.id,
        event_type="earned",
        amount=Decimal("2"),
        currency_code="USD",
        occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
        reward_kind="cashback",
        cashback_rule_id=uuid4(),
    )
    session = _FakeAsyncSession(program, None)

    try:
        await create_reward_event(workspace_id, payload, session)
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Cashback rule not found for this reward program"
    else:
        raise AssertionError("foreign cashback rule should fail")


async def test_create_reward_event_persists_manual_event_with_source_transaction() -> (
    None
):
    workspace_id = uuid4()
    program = _program(workspace_id)
    tx = _transaction(workspace_id)
    payload = RewardEventCreate(
        program_id=program.id,
        event_type="earned",
        amount=Decimal("2"),
        currency_code="USD",
        occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
        source_transaction_id=tx.id,
        reward_kind="cashback",
    )
    session = _FakeAsyncSession(program, tx)

    result = await create_reward_event(workspace_id, payload, session)

    assert isinstance(result, RewardEvent)
    assert result.source_transaction_id == tx.id
    assert result.currency_code == "USD"
    assert session.added == [result]
    assert session.committed is True


async def test_create_reward_event_rejects_source_transaction_outside_workspace() -> (
    None
):
    workspace_id = uuid4()
    program = _program(workspace_id)
    payload = RewardEventCreate(
        program_id=program.id,
        event_type="earned",
        amount=Decimal("2"),
        currency_code="USD",
        occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
        source_transaction_id=uuid4(),
        reward_kind="cashback",
    )
    session = _FakeAsyncSession(program, None)

    try:
        await create_reward_event(workspace_id, payload, session)
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Source transaction not found in this workspace"
    else:
        raise AssertionError("foreign source transaction should fail")


async def test_calculate_expected_reward_endpoint_returns_calculation() -> None:
    workspace_id = uuid4()
    program = _program(workspace_id)
    tx = _transaction(workspace_id)
    rule = _rule(workspace_id, program.id)
    payload = ExpectedRewardRequest(program_id=program.id, source_transaction_id=tx.id)
    session = _FakeAsyncSession(program, tx, [rule])

    result = await calculate_expected_reward(workspace_id, payload, session)

    assert result.amount == Decimal("2.000000")
    assert result.currency_code == "USD"
    assert result.rule_id == rule.id


async def test_list_reward_events_returns_workspace_events() -> None:
    workspace_id = uuid4()
    event = RewardEvent(
        id=uuid4(),
        workspace_id=workspace_id,
        program_id=uuid4(),
        event_type="earned",
        status="posted",
        reward_kind="cashback",
        amount=Decimal("2"),
        currency_code="USD",
        occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
        description="Cashback",
    )
    session = _FakeAsyncSession([event])

    result = await list_reward_events(workspace_id, session)

    assert result == [event]
