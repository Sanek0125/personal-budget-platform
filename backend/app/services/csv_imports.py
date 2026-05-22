import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, time
from decimal import Decimal, InvalidOperation
from io import StringIO
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, field_validator


class CsvColumnMapping(BaseModel):
    """Maps normalized import fields to CSV column names."""

    occurred_at: str
    amount: str
    currency_code: str
    description: str
    type: str | None = None
    booked_at: str | None = None
    merchant_name: str | None = None
    merchant_raw: str | None = None
    external_id: str | None = None
    category_id: str | None = None

    @field_validator("occurred_at", "amount", "currency_code", "description")
    @classmethod
    def require_non_empty_column(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("CSV column names cannot be blank")
        return value


@dataclass(frozen=True)
class ParsedCsvRow:
    row_number: int
    raw_data: dict[str, str]
    normalized_data: dict[str, Any]
    raw_hash: str
    normalized_hash: str


def _stable_hash(data: object) -> str:
    payload = json.dumps(
        data, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _get(
    raw: dict[str, str], column: str | None, *, required: bool = False
) -> str | None:
    if column is None:
        return None
    value = raw.get(column)
    if value is None:
        if required:
            raise HTTPException(status_code=422, detail=f"Missing CSV column: {column}")
        return None
    value = value.strip()
    if required and not value:
        raise HTTPException(
            status_code=422, detail=f"Blank CSV value for column: {column}"
        )
    return value or None


def _parse_datetime(value: str) -> str:
    raw = value.strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            parsed = datetime.strptime(raw, fmt)  # noqa: DTZ007
            if fmt in {"%Y-%m-%d", "%d.%m.%Y"}:
                parsed = datetime.combine(parsed.date(), time.min)
            return parsed.replace(tzinfo=UTC).isoformat()
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail=f"Invalid occurred_at value: {value}"
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.isoformat()


def _parse_amount(value: str) -> Decimal:
    normalized = value.replace(" ", "").replace(",", ".")
    try:
        amount = Decimal(normalized)
    except InvalidOperation as exc:
        raise HTTPException(
            status_code=422, detail=f"Invalid amount value: {value}"
        ) from exc
    if amount == 0:
        raise HTTPException(
            status_code=422, detail="Imported transaction amount must be non-zero"
        )
    return amount


def _transaction_type(raw_type: str | None, amount: Decimal) -> str:
    if raw_type:
        value = raw_type.strip().lower()
        if value not in {"expense", "income", "adjustment"}:
            raise HTTPException(
                status_code=422, detail=f"Unsupported transaction type: {raw_type}"
            )
        if value == "expense" and amount >= 0:
            raise HTTPException(
                status_code=422, detail="Expense amount must be negative"
            )
        if value == "income" and amount <= 0:
            raise HTTPException(
                status_code=422, detail="Income amount must be positive"
            )
        return value
    return "expense" if amount < 0 else "income"


def parse_csv_rows(content: str, mapping: CsvColumnMapping) -> list[ParsedCsvRow]:
    reader = csv.DictReader(StringIO(content))
    if reader.fieldnames is None:
        raise HTTPException(status_code=422, detail="CSV file has no header row")

    rows: list[ParsedCsvRow] = []
    for row_number, raw in enumerate(reader, start=1):
        raw_data = {key: (value or "") for key, value in raw.items() if key is not None}
        amount = _parse_amount(_get(raw_data, mapping.amount, required=True) or "")
        currency_code = (
            _get(raw_data, mapping.currency_code, required=True) or ""
        ).upper()
        if len(currency_code) != 3:
            raise HTTPException(
                status_code=422, detail="Currency code must be 3 characters"
            )
        raw_type = _get(raw_data, mapping.type)
        normalized_data: dict[str, Any] = {
            "type": _transaction_type(raw_type, amount),
            "occurred_at": _parse_datetime(
                _get(raw_data, mapping.occurred_at, required=True) or ""
            ),
            "amount": str(amount),
            "currency_code": currency_code,
            "description": _get(raw_data, mapping.description, required=True),
        }
        optional_fields = {
            "booked_at": _get(raw_data, mapping.booked_at),
            "merchant_name": _get(raw_data, mapping.merchant_name),
            "merchant_raw": _get(raw_data, mapping.merchant_raw),
            "external_id": _get(raw_data, mapping.external_id),
            "category_id": _get(raw_data, mapping.category_id),
        }
        normalized_data.update(
            {key: value for key, value in optional_fields.items() if value}
        )
        rows.append(
            ParsedCsvRow(
                row_number=row_number,
                raw_data=raw_data,
                normalized_data=normalized_data,
                raw_hash=_stable_hash(raw_data),
                normalized_hash=_stable_hash(normalized_data),
            )
        )
    return rows
