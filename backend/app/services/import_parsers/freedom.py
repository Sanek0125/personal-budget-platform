from __future__ import annotations

import csv
from datetime import UTC, datetime, time
from decimal import Decimal, InvalidOperation
from io import StringIO
from typing import Any

from fastapi import HTTPException

from app.services.csv_imports import ParsedCsvRow, _stable_hash

FREEDOM_PARSER_VERSION = "freedom-v1"

_DATE_COLUMNS = (
    "Дата операции",
    "Дата транзакции",
    "Дата",
    "Operation date",
    "Transaction date",
    "Date",
)
_BOOKED_DATE_COLUMNS = (
    "Дата обработки",
    "Дата проводки",
    "Дата списания",
    "Booking date",
    "Processing date",
    "Value date",
)
_DESCRIPTION_COLUMNS = (
    "Описание",
    "Детали",
    "Назначение",
    "Наименование операции",
    "Description",
    "Details",
    "Merchant",
)
_MERCHANT_COLUMNS = (
    "Мерчант",
    "Торговая точка",
    "Merchant",
    "Merchant name",
)
_AMOUNT_COLUMNS = (
    "Сумма",
    "Сумма операции",
    "Сумма в валюте счета",
    "Amount",
    "Transaction amount",
)
_DEBIT_COLUMNS = (
    "Расход",
    "Списание",
    "Дебет",
    "Debit",
    "Withdrawal",
)
_CREDIT_COLUMNS = (
    "Доход",
    "Зачисление",
    "Кредит",
    "Credit",
    "Deposit",
)
_CURRENCY_COLUMNS = (
    "Валюта",
    "Валюта счета",
    "Валюта операции",
    "Currency",
    "Transaction currency",
)
_EXTERNAL_ID_COLUMNS = (
    "ID операции",
    "Номер операции",
    "RRN",
    "ARN",
    "Transaction ID",
    "Reference",
)


def _read_rows(content: str) -> list[dict[str, str]]:
    sample = content[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
        if sample.count(";") > sample.count(","):
            dialect.delimiter = ";"
    reader = csv.DictReader(StringIO(content), dialect=dialect)
    if reader.fieldnames is None:
        raise HTTPException(
            status_code=422,
            detail="Freedom statement has no header row",
        )
    return [
        {key.strip(): (value or "").strip() for key, value in row.items() if key}
        for row in reader
    ]


def _pick(
    raw: dict[str, str], candidates: tuple[str, ...], *, required: bool = False
) -> str | None:
    folded = {key.strip().lower(): key for key in raw}
    for candidate in candidates:
        key = folded.get(candidate.lower())
        if key is not None:
            value = raw[key].strip()
            if value:
                return value
            if required:
                raise HTTPException(
                    status_code=422,
                    detail=f"Blank Freedom value for column: {key}",
                )
    if required:
        raise HTTPException(
            status_code=422,
            detail=f"Missing Freedom column: {'/'.join(candidates)}",
        )
    return None


def _parse_datetime(value: str) -> str:
    raw = value.strip()
    for fmt in (
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            parsed = datetime.strptime(raw, fmt)  # noqa: DTZ007
        except ValueError:
            continue
        if fmt in {"%d.%m.%Y", "%Y-%m-%d"}:
            parsed = datetime.combine(parsed.date(), time.min)
        return parsed.replace(tzinfo=UTC).isoformat()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid Freedom date value: {value}",
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.isoformat()


def _parse_amount(value: str) -> Decimal:
    normalized = (
        value.replace("\u00a0", "")
        .replace(" ", "")
        .replace("−", "-")
        .replace(",", ".")
    )
    try:
        amount = Decimal(normalized)
    except InvalidOperation as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid Freedom amount value: {value}",
        ) from exc
    if amount == 0:
        raise HTTPException(
            status_code=422,
            detail="Imported transaction amount must be non-zero",
        )
    return amount


def _amount(raw: dict[str, str]) -> Decimal:
    amount = _pick(raw, _AMOUNT_COLUMNS)
    if amount is not None:
        return _parse_amount(amount)

    debit = _pick(raw, _DEBIT_COLUMNS)
    credit = _pick(raw, _CREDIT_COLUMNS)
    if debit and credit:
        raise HTTPException(
            status_code=422,
            detail="Freedom row cannot have both debit and credit amounts",
        )
    if debit:
        return -abs(_parse_amount(debit))
    if credit:
        return abs(_parse_amount(credit))
    raise HTTPException(status_code=422, detail="Missing Freedom amount column")


def _currency(raw: dict[str, str]) -> str:
    currency_code = (_pick(raw, _CURRENCY_COLUMNS, required=True) or "").upper()
    if len(currency_code) != 3:
        raise HTTPException(
            status_code=422,
            detail="Currency code must be 3 characters",
        )
    return currency_code


def _normalized(raw: dict[str, str]) -> dict[str, Any]:
    amount = _amount(raw)
    description = _pick(raw, _DESCRIPTION_COLUMNS, required=True)
    normalized: dict[str, Any] = {
        "type": "expense" if amount < 0 else "income",
        "occurred_at": _parse_datetime(_pick(raw, _DATE_COLUMNS, required=True) or ""),
        "amount": str(amount),
        "currency_code": _currency(raw),
        "description": description,
    }
    booked_at = _pick(raw, _BOOKED_DATE_COLUMNS)
    if booked_at:
        normalized["booked_at"] = _parse_datetime(booked_at)
    merchant = _pick(raw, _MERCHANT_COLUMNS) or description
    if merchant:
        normalized["merchant_raw"] = merchant
    external_id = _pick(raw, _EXTERNAL_ID_COLUMNS)
    if external_id:
        normalized["external_id"] = external_id
    return normalized


def parse_freedom_rows(content: str) -> list[ParsedCsvRow]:
    rows: list[ParsedCsvRow] = []
    for row_number, raw_data in enumerate(_read_rows(content), start=1):
        normalized_data = _normalized(raw_data)
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
