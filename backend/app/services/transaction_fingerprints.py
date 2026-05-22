"""Deterministic duplicate-detection fingerprints for transactions.

A transaction *fingerprint* is a stable SHA-256 hash that backs the partial
unique index ``uq_transactions_active_fingerprint``. Keep the algorithm
backward-compatible with the fingerprints produced when the transactions schema
was introduced, otherwise already-stored rows would not deduplicate against new
writes without a data backfill.
"""

from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

__all__ = ["build_transaction_fingerprint", "decimal_fingerprint_text"]


def decimal_fingerprint_text(value: Decimal) -> str:
    """Render a Decimal exactly as the original transaction fingerprint did."""
    return str(value.normalize())


def build_transaction_fingerprint(
    *,
    workspace_id: UUID,
    account_id: UUID,
    type: str,
    occurred_at: datetime,
    amount: Decimal,
    currency_code: str,
    description: str,
    external_id: str | None = None,
) -> str:
    """Build the backward-compatible duplicate-detection fingerprint.

    The field order, separator, and decimal rendering intentionally match the
    original route-local implementation from the transactions feature. Any
    future semantic change must include a migration/backfill plan for existing
    ``transactions.fingerprint`` values.
    """
    raw = "|".join(
        [
            str(workspace_id),
            str(account_id),
            type,
            occurred_at.isoformat(),
            decimal_fingerprint_text(amount),
            currency_code,
            description,
            external_id or "",
        ]
    )
    return sha256(raw.encode("utf-8")).hexdigest()
