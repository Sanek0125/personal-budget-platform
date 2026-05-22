from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, Index, UniqueConstraint, inspect

from app.api.category_rules import (
    apply_category_rules,
    create_category_rule,
    list_category_rules,
    update_category_rule,
)
from app.db.base import Base
from app.models import Category, CategoryRule, CategoryRuleMatch, Transaction
from app.schemas.category_rule import CategoryRuleCreate, CategoryRuleUpdate
from app.services.category_rules import (
    OPERATOR_PRIORITY,
    find_matching_rule,
    rule_matches,
)


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
    def __init__(
        self,
        *results: object | list[object] | None,
        commit_exception: Exception | None = None,
    ) -> None:
        self.results = list(results)
        self.commit_exception = commit_exception
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
        if self.commit_exception is not None:
            raise self.commit_exception
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def refresh(
        self, obj: object, attribute_names: list[str] | None = None
    ) -> None:
        del attribute_names
        self.refreshed.append(obj)


def _rule(
    workspace_id=None,
    *,
    operator="contains",
    pattern="coffee",
    match_field="description",
    amount_min=None,
    amount_max=None,
    priority=100,
    category_id=None,
    rule_id=None,
    is_active=True,
) -> CategoryRule:
    return CategoryRule(
        id=rule_id or uuid4(),
        workspace_id=workspace_id or uuid4(),
        category_id=category_id or uuid4(),
        name="Coffee rule",
        operator=operator,
        match_field=match_field,
        pattern=pattern,
        amount_min=amount_min,
        amount_max=amount_max,
        priority=priority,
        is_active=is_active,
    )


def _transaction(
    workspace_id=None,
    *,
    description="Morning Coffee",
    merchant_name=None,
    merchant_raw=None,
    amount=Decimal("-4.50"),
    category_id=None,
) -> Transaction:
    return Transaction(
        id=uuid4(),
        workspace_id=workspace_id or uuid4(),
        account_id=uuid4(),
        type="expense" if amount < 0 else "income",
        amount=amount,
        currency_code="USD",
        description=description,
        merchant_name=merchant_name,
        merchant_raw=merchant_raw,
        category_id=category_id,
        source="manual",
        fingerprint="fp",
    )


# --- models -----------------------------------------------------------------


def test_category_rule_models_are_registered_with_metadata() -> None:
    assert CategoryRule.__tablename__ == "category_rules"
    assert CategoryRuleMatch.__tablename__ == "category_rule_matches"
    assert {"category_rules", "category_rule_matches"}.issubset(Base.metadata.tables)


def test_category_rule_models_have_expected_constraints_and_indexes() -> None:
    rules = Base.metadata.tables["category_rules"]
    matches = Base.metadata.tables["category_rule_matches"]

    rule_checks = {c.name for c in rules.constraints if isinstance(c, CheckConstraint)}
    rule_indexes = {i.name for i in rules.indexes if isinstance(i, Index)}
    match_uniques = {
        c.name for c in matches.constraints if isinstance(c, UniqueConstraint)
    }
    match_indexes = {i.name for i in matches.indexes if isinstance(i, Index)}

    assert {
        "ck_category_rules_operator",
        "ck_category_rules_match_field",
        "ck_category_rules_definition",
    }.issubset(rule_checks)
    assert {
        "ix_category_rules_workspace_id",
        "ix_category_rules_category_id",
    }.issubset(rule_indexes)
    assert "uq_category_rule_matches_rule_transaction" in match_uniques
    assert {
        "ix_category_rule_matches_workspace_id",
        "ix_category_rule_matches_transaction_id",
    }.issubset(match_indexes)


def test_category_rule_relationships_are_configured() -> None:
    rule_relationships = {rel.key for rel in inspect(CategoryRule).relationships}
    match_relationships = {rel.key for rel in inspect(CategoryRuleMatch).relationships}

    assert {"workspace", "category", "matches"}.issubset(rule_relationships)
    assert {"workspace", "rule", "transaction"}.issubset(match_relationships)


# --- matching service -------------------------------------------------------


def test_rule_matches_contains_is_case_insensitive() -> None:
    rule = _rule(operator="contains", pattern="coffee")
    assert rule_matches(rule, _transaction(description="Morning COFFEE run")) is True
    assert rule_matches(rule, _transaction(description="Tea house")) is False


def test_rule_matches_equals() -> None:
    rule = _rule(operator="equals", pattern="Salary")
    assert rule_matches(rule, _transaction(description="salary")) is True
    assert rule_matches(rule, _transaction(description="Salary bonus")) is False


def test_rule_matches_starts_with() -> None:
    rule = _rule(operator="starts_with", pattern="ATM")
    assert rule_matches(rule, _transaction(description="ATM withdrawal")) is True
    assert rule_matches(rule, _transaction(description="Card ATM")) is False


def test_rule_matches_regex() -> None:
    rule = _rule(operator="regex", pattern=r"uber\s*eats")
    assert rule_matches(rule, _transaction(description="uber eats order")) is True
    assert rule_matches(rule, _transaction(description="uberX ride")) is False


def test_rule_matches_amount_between() -> None:
    rule = _rule(
        operator="amount_between",
        pattern=None,
        amount_min=Decimal("-100"),
        amount_max=Decimal("-10"),
    )
    assert rule_matches(rule, _transaction(amount=Decimal("-50"))) is True
    assert rule_matches(rule, _transaction(amount=Decimal("-5"))) is False


def test_rule_matches_uses_configured_match_field() -> None:
    rule = _rule(operator="contains", pattern="starbucks", match_field="merchant_name")
    assert rule_matches(
        rule, _transaction(description="coffee", merchant_name="Starbucks #12")
    ) is True
    assert rule_matches(rule, _transaction(description="Starbucks")) is False


def test_find_matching_rule_uses_operator_priority_order() -> None:
    assert OPERATOR_PRIORITY["contains"] < OPERATOR_PRIORITY["amount_between"]
    workspace_id = uuid4()
    contains_rule = _rule(workspace_id, operator="contains", pattern="coffee")
    amount_rule = _rule(
        workspace_id,
        operator="amount_between",
        pattern=None,
        amount_min=Decimal("-100"),
        amount_max=Decimal("0"),
    )
    transaction = _transaction(workspace_id, description="coffee", amount=Decimal("-5"))

    winner = find_matching_rule([amount_rule, contains_rule], transaction)
    assert winner is contains_rule


def test_find_matching_rule_respects_explicit_priority() -> None:
    workspace_id = uuid4()
    contains_rule = _rule(
        workspace_id, operator="contains", pattern="coffee", priority=100
    )
    regex_rule = _rule(
        workspace_id, operator="regex", pattern="coffee", priority=10
    )
    transaction = _transaction(workspace_id, description="coffee")

    winner = find_matching_rule([contains_rule, regex_rule], transaction)
    assert winner is regex_rule


def test_find_matching_rule_returns_none_when_no_rule_matches() -> None:
    rule = _rule(operator="contains", pattern="coffee")
    assert find_matching_rule([rule], _transaction(description="Groceries")) is None


# --- schemas ----------------------------------------------------------------


def test_category_rule_create_requires_pattern_for_text_operator() -> None:
    with pytest.raises(ValidationError):
        CategoryRuleCreate(name="r", category_id=uuid4(), operator="contains")


def test_category_rule_create_requires_bounds_for_amount_between() -> None:
    with pytest.raises(ValidationError):
        CategoryRuleCreate(
            name="r", category_id=uuid4(), operator="amount_between"
        )


def test_category_rule_create_rejects_invalid_regex() -> None:
    with pytest.raises(ValidationError):
        CategoryRuleCreate(
            name="r", category_id=uuid4(), operator="regex", pattern="[unclosed"
        )


def test_category_rule_create_accepts_valid_definition() -> None:
    payload = CategoryRuleCreate(
        name="Coffee",
        category_id=uuid4(),
        operator="contains",
        pattern="coffee",
    )
    assert payload.match_field == "description"
    assert payload.priority == 100
    assert payload.is_active is True


# --- endpoints --------------------------------------------------------------


async def test_create_category_rule_persists_rule() -> None:
    workspace_id = uuid4()
    category_id = uuid4()
    session = _FakeAsyncSession(workspace_id, category_id)

    rule = await create_category_rule(
        workspace_id,
        CategoryRuleCreate(
            name="Coffee",
            category_id=category_id,
            operator="contains",
            pattern="coffee",
        ),
        session,  # type: ignore[arg-type]
    )

    assert session.added == [rule]
    assert session.committed is True
    assert rule.workspace_id == workspace_id
    assert rule.category_id == category_id


async def test_create_category_rule_rejects_unknown_category() -> None:
    workspace_id = uuid4()
    session = _FakeAsyncSession(workspace_id, None)

    with pytest.raises(HTTPException) as exc:
        await create_category_rule(
            workspace_id,
            CategoryRuleCreate(
                name="Coffee",
                category_id=uuid4(),
                operator="contains",
                pattern="coffee",
            ),
            session,  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 404


async def test_list_category_rules_returns_rules() -> None:
    workspace_id = uuid4()
    rules = [_rule(workspace_id), _rule(workspace_id)]
    session = _FakeAsyncSession(rules)

    result = await list_category_rules(workspace_id, session)  # type: ignore[arg-type]
    assert result == rules


async def test_update_category_rule_applies_changes() -> None:
    rule = _rule()
    session = _FakeAsyncSession(rule)

    updated = await update_category_rule(
        rule.id,
        CategoryRuleUpdate(name="Renamed", priority=5, is_active=False),
        session,  # type: ignore[arg-type]
    )

    assert updated.name == "Renamed"
    assert updated.priority == 5
    assert updated.is_active is False
    assert session.committed is True


async def test_update_category_rule_missing_returns_404() -> None:
    session = _FakeAsyncSession(None)

    with pytest.raises(HTTPException) as exc:
        await update_category_rule(
            uuid4(),
            CategoryRuleUpdate(name="Renamed"),
            session,  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 404


async def test_update_category_rule_rejects_invalid_definition() -> None:
    rule = _rule(operator="contains", pattern="coffee")
    session = _FakeAsyncSession(rule)

    with pytest.raises(HTTPException) as exc:
        await update_category_rule(
            rule.id,
            CategoryRuleUpdate(operator="amount_between", pattern=None),
            session,  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 422


async def test_apply_category_rules_categorizes_uncategorized_transactions() -> None:
    workspace_id = uuid4()
    category_id = uuid4()
    rule = _rule(workspace_id, operator="contains", pattern="coffee",
                 category_id=category_id)
    matched = _transaction(workspace_id, description="Morning Coffee")
    unmatched = _transaction(workspace_id, description="Salary")
    session = _FakeAsyncSession(workspace_id, [rule], [matched, unmatched])

    result = await apply_category_rules(workspace_id, session)  # type: ignore[arg-type]

    assert result.evaluated_count == 2
    assert result.categorized_count == 1
    assert result.transaction_ids == [matched.id]
    assert matched.category_id == category_id
    assert matched.categorized_by == "rule"
    assert unmatched.category_id is None
    assert any(isinstance(obj, CategoryRuleMatch) for obj in session.added)
    assert session.committed is True


def test_category_helper_is_available() -> None:
    # Category import is exercised so the suite fails loudly if the model
    # registry changes shape.
    assert Category.__tablename__ == "categories"
