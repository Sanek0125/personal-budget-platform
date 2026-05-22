"""Unit tests for deterministic transaction duplicate fingerprints."""

from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

from app.db.base import Base
from app.services.transaction_fingerprints import (
    build_transaction_fingerprint,
    decimal_fingerprint_text,
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
        "external_id": None,
    }
    params.update(overrides)
    return build_transaction_fingerprint(**params)


def test_decimal_fingerprint_text_matches_legacy_normalize_rendering() -> None:
    assert decimal_fingerprint_text(Decimal("-12.00")) == "-12"
    assert decimal_fingerprint_text(Decimal("100.00")) == "1E+2"


def test_fingerprint_is_deterministic() -> None:
    assert _fingerprint() == _fingerprint()


def test_fingerprint_is_sha256_hex() -> None:
    value = _fingerprint()
    assert len(value) == 64
    assert all(char in "0123456789abcdef" for char in value)


def test_fingerprint_matches_legacy_route_algorithm() -> None:
    workspace_id = UUID(int=1)
    account_id = UUID(int=2)
    raw = "|".join(
        [
            str(workspace_id),
            str(account_id),
            "expense",
            _OCCURRED_AT.isoformat(),
            str(Decimal("-12.00").normalize()),
            "USD",
            "Coffee Shop",
            "",
        ]
    )

    assert _fingerprint(workspace_id=workspace_id, account_id=account_id) == sha256(
        raw.encode("utf-8")
    ).hexdigest()


def test_amount_scale_matches_legacy_behavior() -> None:
    assert _fingerprint(amount=Decimal("-12.0")) == _fingerprint(
        amount=Decimal("-12.000000")
    )


def test_description_case_and_whitespace_match_legacy_behavior() -> None:
    assert _fingerprint(description="Coffee Shop") != _fingerprint(
        description="  coffee    SHOP "
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


def test_external_id_participates_in_legacy_fingerprint() -> None:
    base = _fingerprint(external_id="BANK-001")
    assert base != _fingerprint(external_id="BANK-002")
    assert base != _fingerprint(external_id=None)
    assert base != _fingerprint(
        external_id="BANK-001",
        amount=Decimal("-999.99"),
        occurred_at=datetime(2000, 1, 1, tzinfo=UTC),
        description="totally different",
    )


def test_blank_external_id_matches_legacy_empty_string_behavior() -> None:
    assert _fingerprint(external_id="") == _fingerprint(external_id=None)
    assert _fingerprint(external_id="   ") != _fingerprint(external_id=None)


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
