from __future__ import annotations

import csv
import re
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
_PDF_DATE_LINE_RE = re.compile(
    r"^\s*(?P<date>\d{2}\.\d{2}\.\d{4})\s+(?P<document>\d+)\b"
)
_PDF_AMOUNT_RE = re.compile(r"\d[\d ]*(?:[.,]\d{2})?")


def _looks_like_freedom_pdf_text(content: str) -> bool:
    return (
        "Выписка по" in content
        and "Дата" in content
        and "Дебет" in content
        and "Кредит" in content
        and "Назначение платежа" in content
    )


def _statement_currency(content: str) -> str:
    match = re.search(r"(?im)^\s*Валюта:\s*([A-Z]{3})\s*$", content)
    if match:
        return match.group(1).upper()
    raise HTTPException(status_code=422, detail="Missing Freedom statement currency")


def _statement_column_positions(lines: list[str]) -> tuple[int, int, int]:
    for line in lines:
        if "Дебет" in line and "Кредит" in line:
            return line.index("Дебет"), line.index("Кредит"), line.index("Назначение")
    raise HTTPException(status_code=422, detail="Missing Freedom PDF amount header")


def _is_amount_token_in_column(
    token_start: int, column_start: int, next_column_start: int
) -> bool:
    return column_start - 2 <= token_start < next_column_start - 1


def _tokens_in_column(
    block: list[str], column_start: int, next_column_start: int
) -> list[str]:
    tokens: list[str] = []
    for line in block:
        for match in _PDF_AMOUNT_RE.finditer(line):
            if _is_amount_token_in_column(
                match.start(), column_start, next_column_start
            ):
                tokens.append(match.group(0))
    return tokens


def _pdf_amount(
    block: list[str], debit_col: int, credit_col: int, description_col: int
) -> Decimal:
    debit_tokens = _tokens_in_column(block, debit_col, credit_col)
    credit_tokens = _tokens_in_column(block, credit_col, description_col)
    if debit_tokens and credit_tokens:
        raise HTTPException(
            status_code=422,
            detail="Freedom PDF row cannot have both debit and credit amounts",
        )
    if debit_tokens:
        return -abs(_parse_amount("".join(debit_tokens)))
    if credit_tokens:
        return abs(_parse_amount("".join(credit_tokens)))
    raise HTTPException(status_code=422, detail="Missing Freedom PDF amount")


def _pdf_raw_description(block: list[str], description_col: int) -> str:
    description_start = max(0, description_col - 2)
    parts = [
        line[description_start:].strip()
        for line in block
        if len(line) > description_start
    ]
    return re.sub(r"\s+", " ", " ".join(part for part in parts if part)).strip()


def _pdf_description(block: list[str], description_col: int) -> str:
    description = _pdf_raw_description(block, description_col)
    if description.startswith("операция:"):
        description = description.removeprefix("операция:").strip()
    elif " операция: " in description:
        description = description.split(" операция: ", 1)[1].strip()
    if not description:
        raise HTTPException(status_code=422, detail="Missing Freedom PDF description")
    return description


def _pdf_occurred_at(row_date: str, description: str) -> str:
    transaction_time = re.search(
        r"транзакции:\s*(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2}:\d{2})",
        description,
        flags=re.IGNORECASE,
    )
    if transaction_time:
        return _parse_datetime(
            f"{transaction_time.group(1)} {transaction_time.group(2)}"
        )
    return _parse_datetime(row_date)


def _pdf_external_id(document_number: str, description: str) -> str:
    rrn = re.search(r"РРН[:\s]*([0-9A-Za-z-]+)", description, flags=re.IGNORECASE)
    if rrn:
        return rrn.group(1)
    return document_number


def _parse_freedom_pdf_text_rows(content: str) -> list[ParsedCsvRow]:
    lines = content.splitlines()
    debit_col, credit_col, description_col = _statement_column_positions(lines)
    currency_code = _statement_currency(content)
    date_line_indexes = [
        index for index, line in enumerate(lines) if _PDF_DATE_LINE_RE.match(line)
    ]
    if not date_line_indexes:
        raise HTTPException(status_code=422, detail="Freedom PDF statement has no rows")

    parsed_rows: list[ParsedCsvRow] = []
    for row_number, date_line_index in enumerate(date_line_indexes, start=1):
        date_match = _PDF_DATE_LINE_RE.match(lines[date_line_index])
        if date_match is None:
            continue
        block_start = date_line_index
        while block_start > 0 and lines[block_start - 1].strip():
            block_start -= 1
        block_end = date_line_index + 1
        while block_end < len(lines) and lines[block_end].strip():
            block_end += 1
        block = lines[block_start:block_end]
        amount = _pdf_amount(block, debit_col, credit_col, description_col)
        raw_description = _pdf_raw_description(block, description_col)
        description = _pdf_description(block, description_col)
        document_number = date_match.group("document")
        normalized_data: dict[str, Any] = {
            "type": "expense" if amount < 0 else "income",
            "occurred_at": _pdf_occurred_at(date_match.group("date"), raw_description),
            "amount": str(amount),
            "currency_code": currency_code,
            "description": description,
            "merchant_raw": description,
            "external_id": _pdf_external_id(document_number, description),
        }
        raw_data = {
            "statement_format": "freedom_pdf_text",
            "operation_date": date_match.group("date"),
            "document_number": document_number,
            "debit": "".join(_tokens_in_column(block, debit_col, credit_col)),
            "credit": "".join(_tokens_in_column(block, credit_col, description_col)),
            "currency_code": currency_code,
            "description": description,
        }
        parsed_rows.append(
            ParsedCsvRow(
                row_number=row_number,
                raw_data=raw_data,
                normalized_data=normalized_data,
                raw_hash=_stable_hash(raw_data),
                normalized_hash=_stable_hash(normalized_data),
            )
        )
    return parsed_rows


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
    if _looks_like_freedom_pdf_text(content):
        return _parse_freedom_pdf_text_rows(content)

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
