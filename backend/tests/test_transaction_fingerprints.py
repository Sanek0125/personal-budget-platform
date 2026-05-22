"""Unit tests for deterministic transaction duplicate fingerprints."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from app.db.base import Base
from app.services.transaction_fingerprints import (
    build_transaction_fingerprint,
    normalize_amount,
    normalize_currency_code,
    normalize_description,
    normalize_external_id,
    normalize_whitespace,
)

_OCCURRED_AT = datetime(2026, 5, 21, 9, 30, tzinfo=UTC)


def _fingerprint(**overrides: object) -> str:
    params: dict[str, object] = {
        "workspace_id": UUID(int=1),
        "account_id": UUID(int=2),
        "type": "expense",
        "occurred_at": _OCCURRED_AT,
        "amount": Decimal("-12.00"),
        "currency_code": "USD",
        "description": "Coffee Shop",
        "source": "manual",
        "external_id": None,
    }
    params.update(overrides)
    return build_transaction_fingerprint(**params)


# --- normalization helpers -------------------------------------------------


def test_normalize_whitespace_trims_and_collapses() -> None:
    assert normalize_whitespace("  Coffee \t  Shop  ") == "Coffee Shop"


def test_normalize_description_collapses_whitespace_and_uppercases() -> None:
    assert normalize_description("  flat   white ") == "FLAT WHITE"


def test_normalize_currency_code_trims_and_uppercases() -> None:
    assert normalize_currency_code(" usd ") == "USD"


def test_normalize_amount_is_scale_independent() -> None:
    assert normalize_amount(Decimal("-12.0")) == normalize_amount(
        Decimal("-12.000000")
    )


def test_normalize_amount_keeps_significant_digits() -> None:
    assert normalize_amount(Decimal("-12.34")) != normalize_amount(Decimal("-12.00"))


def test_normalize_amount_uses_plain_notation() -> None:
    assert normalize_amount(Decimal("100")) == "100"


def test_normalize_amount_collapses_negative_zero() -> None:
    assert normalize_amount(Decimal("-0.00")) == normalize_amount(Decimal("0"))


def test_normalize_external_id_trims_and_blanks_to_none() -> None:
    assert normalize_external_id("  bank-1 ") == "bank-1"
    assert normalize_external_id("   ") is None
    assert normalize_external_id(None) is None


# --- intrinsic fingerprint -------------------------------------------------


def test_fingerprint_is_deterministic() -> None:
    assert _fingerprint() == _fingerprint()


def test_fingerprint_is_sha256_hex() -> None:
    value = _fingerprint()
    assert len(value) == 64
    assert all(char in "0123456789abcdef" for char in value)


def test_same_logical_transaction_ignores_whitespace_case_and_scale() -> None:
    assert _fingerprint() == _fingerprint(
        description="  coffee    SHOP ",
        amount=Decimal("-12.000000"),
        currency_code="usd",
    )


def test_distinct_description_produces_distinct_fingerprint() -> None:
    assert _fingerprint(description="Coffee Shop") != _fingerprint(
        description="Tea Shop"
    )


def test_distinct_amount_produces_distinct_fingerprint() -> None:
    assert _fingerprint(amount=Decimal("-12.00")) != _fingerprint(
        amount=Decimal("-13.00")
    )


def test_distinct_occurred_at_produces_distinct_fingerprint() -> None:
    other = datetime(2026, 5, 22, 9, 30, tzinfo=UTC)
    assert _fingerprint() != _fingerprint(occurred_at=other)


def test_fingerprint_is_scoped_to_account_and_workspace() -> None:
    base = _fingerprint()
    assert base != _fingerprint(account_id=UUID(int=999))
    assert base != _fingerprint(workspace_id=UUID(int=999))


# --- external-id fingerprint ----------------------------------------------


def test_external_id_fingerprint_ignores_description_noise() -> None:
    base = _fingerprint(external_id="BANK-001")
    assert base == _fingerprint(
        external_id="BANK-001", description="  totally   different TEXT "
    )
    assert base == _fingerprint(external_id="  BANK-001 ")


def test_external_id_fingerprint_ignores_amount_and_time() -> None:
    base = _fingerprint(external_id="BANK-001")
    assert base == _fingerprint(
        external_id="BANK-001",
        amount=Decimal("-999.99"),
        occurred_at=datetime(2000, 1, 1, tzinfo=UTC),
    )


def test_external_id_fingerprint_is_scoped() -> None:
    base = _fingerprint(external_id="BANK-001")
    assert base != _fingerprint(external_id="BANK-001", account_id=UUID(int=999))
    assert base != _fingerprint(external_id="BANK-001", workspace_id=UUID(int=999))
    assert base != _fingerprint(external_id="BANK-001", source="csv_import")


def test_external_id_fingerprint_distinguishes_ids() -> None:
    assert _fingerprint(external_id="BANK-001") != _fingerprint(
        external_id="BANK-002"
    )


def test_blank_external_id_falls_back_to_intrinsic_fingerprint() -> None:
    assert _fingerprint(external_id="   ") == _fingerprint(external_id=None)


def test_external_and_intrinsic_modes_do_not_collide() -> None:
    assert _fingerprint(external_id="x") != _fingerprint(external_id=None)


# --- soft-delete reimport --------------------------------------------------


def test_active_fingerprint_index_excludes_soft_deleted_rows() -> None:
    """The unique fingerprint index is partial on ``deleted_at IS NULL``.

    A soft-deleted duplicate therefore does not block re-creating or
    re-importing the same logical transaction.
    """
    index = next(
        ix
        for ix in Base.metadata.tables["transactions"].indexes
        if ix.name == "uq_transactions_active_fingerprint"
    )
    assert index.unique is True
    where = str(index.dialect_options["postgresql"]["where"])
    assert "deleted_at IS NULL" in where
