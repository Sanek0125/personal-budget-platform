"""Deterministic duplicate-detection fingerprints for transactions.

A transaction *fingerprint* is a stable SHA-256 hash that backs the partial
unique index ``uq_transactions_active_fingerprint``. Two transactions that
represent the same logical event must always hash to the same value, so all
normalization rules live here instead of being duplicated across route
handlers.
"""

import re
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

__all__ = [
    "build_transaction_fingerprint",
    "normalize_amount",
    "normalize_currency_code",
    "normalize_description",
    "normalize_external_id",
    "normalize_whitespace",
]

# Bumping this invalidates every previously stored fingerprint, so change it
# only together with a backfill plan.
_FINGERPRINT_VERSION = "v1"
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_whitespace(value: str) -> str:
    """Trim surrounding whitespace and collapse internal runs to one space."""
    return _WHITESPACE_RE.sub(" ", value).strip()


def normalize_description(value: str) -> str:
    """Whitespace-normalize and uppercase a description for fingerprinting."""
    return normalize_whitespace(value).upper()


def normalize_currency_code(value: str) -> str:
    """Normalize a currency code to its trimmed uppercase form."""
    return value.strip().upper()


def normalize_amount(value: Decimal) -> str:
    """Render a monetary amount in a scale-independent canonical text form.

    ``Decimal("-12.0")`` and ``Decimal("-12.000000")`` are the same amount of
    money and must produce identical text. ``normalize()`` strips trailing
    zeros; the ``"f"`` format then keeps plain (non-exponential) digits so
    large integers stay readable.
    """
    normalized = value.normalize()
    if normalized == 0:
        # Collapse a possible negative zero to a single canonical form.
        normalized = Decimal(0)
    return format(normalized, "f")


def normalize_external_id(value: str | None) -> str | None:
    """Trim an external id, treating blank/whitespace-only values as absent."""
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def build_transaction_fingerprint(
    *,
    workspace_id: UUID,
    account_id: UUID,
    type: str,
    occurred_at: datetime,
    amount: Decimal,
    currency_code: str,
    description: str,
    source: str,
    external_id: str | None = None,
) -> str:
    """Build the deterministic duplicate-detection fingerprint.

    When ``external_id`` is present (non-empty after trimming) the fingerprint
    identifies only the workspace/account/source/external-id tuple, so
    re-importing the same source row collapses to a duplicate regardless of
    description casing, spacing, or amount scale. Otherwise the intrinsic
    transaction fields are used.
    """
    cleaned_external_id = normalize_external_id(external_id)
    if cleaned_external_id is not None:
        segments = [
            _FINGERPRINT_VERSION,
            "external",
            str(workspace_id),
            str(account_id),
            source.strip(),
            cleaned_external_id,
        ]
    else:
        segments = [
            _FINGERPRINT_VERSION,
            "intrinsic",
            str(workspace_id),
            str(account_id),
            type,
            occurred_at.isoformat(),
            normalize_amount(amount),
            normalize_currency_code(currency_code),
            normalize_description(description),
            source.strip(),
        ]
    return sha256("\n".join(segments).encode("utf-8")).hexdigest()
