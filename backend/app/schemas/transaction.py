from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

TransactionType = Literal["expense", "income", "transfer", "adjustment"]
ManualTransactionType = Literal["expense", "income", "adjustment"]
TransactionStatus = Literal["posted", "pending", "deleted", "duplicate", "ignored"]
TransactionSource = Literal[
    "manual", "csv_import", "excel_import", "pdf_import", "telegram", "api"
]
ManualTransactionSource = Literal["manual", "api"]
TransactionLinkRelationType = Literal[
    "transfer_pair",
    "refund",
    "cashback_for",
    "correction",
    "duplicate_of",
    "debt_payment_for",
]
MoneyAmount = Annotated[Decimal, Field(max_digits=20, decimal_places=6)]
ExchangeRateAmount = Annotated[Decimal, Field(max_digits=24, decimal_places=12)]


def _uppercase_currency(value: str | None) -> str | None:
    if value is None:
        return None
    return value.upper()


class TransactionSplitCreate(BaseModel):
    category_id: UUID
    amount: MoneyAmount
    currency_code: str = Field(min_length=3, max_length=3)
    description: str | None = None
    sort_order: int = 0

    @field_validator("currency_code")
    @classmethod
    def normalize_currency_code(cls, value: str) -> str:
        return value.upper()


class TransactionSplitRead(TransactionSplitCreate):
    id: UUID
    transaction_id: UUID

    model_config = {"from_attributes": True}


class TransactionCreate(BaseModel):
    account_id: UUID
    type: ManualTransactionType
    occurred_at: datetime
    booked_at: date | None = None
    amount: MoneyAmount
    currency_code: str = Field(min_length=3, max_length=3)
    original_amount: MoneyAmount | None = None
    original_currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    base_amount: MoneyAmount | None = None
    base_currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    exchange_rate_id: UUID | None = None
    exchange_rate: ExchangeRateAmount | None = None
    description: str = Field(min_length=1)
    merchant_name: str | None = None
    merchant_raw: str | None = None
    category_id: UUID | None = None
    notes: str | None = None
    source: ManualTransactionSource = "manual"
    external_id: str | None = None
    splits: list[TransactionSplitCreate] = Field(default_factory=list)

    @field_validator("currency_code", "original_currency_code", "base_currency_code")
    @classmethod
    def normalize_currency_codes(cls, value: str | None) -> str | None:
        return _uppercase_currency(value)

    @model_validator(mode="after")
    def validate_sign(self) -> "TransactionCreate":
        if self.type == "expense" and self.amount >= 0:
            raise ValueError("Expense amount must be negative")
        if self.type == "income" and self.amount <= 0:
            raise ValueError("Income amount must be positive")
        if self.type == "adjustment" and self.amount == 0:
            raise ValueError("Adjustment amount must be non-zero")
        return self


class TransactionUpdate(BaseModel):
    occurred_at: datetime | None = None
    booked_at: date | None = None
    amount: MoneyAmount | None = None
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    original_amount: MoneyAmount | None = None
    original_currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    base_amount: MoneyAmount | None = None
    base_currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    exchange_rate_id: UUID | None = None
    exchange_rate: ExchangeRateAmount | None = None
    description: str | None = Field(default=None, min_length=1)
    merchant_name: str | None = None
    merchant_raw: str | None = None
    category_id: UUID | None = None
    notes: str | None = None
    splits: list[TransactionSplitCreate] | None = None

    @field_validator("currency_code", "original_currency_code", "base_currency_code")
    @classmethod
    def normalize_currency_codes(cls, value: str | None) -> str | None:
        return _uppercase_currency(value)


class TransactionRead(BaseModel):
    id: UUID
    workspace_id: UUID
    account_id: UUID
    user_id: UUID | None = None
    type: TransactionType
    status: TransactionStatus
    occurred_at: datetime
    booked_at: date | None = None
    amount: MoneyAmount
    currency_code: str
    original_amount: MoneyAmount | None = None
    original_currency_code: str | None = None
    base_amount: MoneyAmount | None = None
    base_currency_code: str | None = None
    exchange_rate_id: UUID | None = None
    exchange_rate: ExchangeRateAmount | None = None
    description: str
    merchant_name: str | None = None
    merchant_raw: str | None = None
    category_id: UUID | None = None
    category_confidence: Decimal | None = None
    categorized_by: str | None = None
    notes: str | None = None
    source: TransactionSource
    external_id: str | None = None
    fingerprint: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
    splits: list[TransactionSplitRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class TransferCreate(BaseModel):
    from_account_id: UUID
    to_account_id: UUID
    occurred_at: datetime
    from_amount: MoneyAmount
    from_currency_code: str = Field(min_length=3, max_length=3)
    to_amount: MoneyAmount | None = None
    to_currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    exchange_rate: ExchangeRateAmount | None = None
    exchange_rate_id: UUID | None = None
    description: str = Field(min_length=1)
    notes: str | None = None
    booked_at: date | None = None

    @field_validator("from_currency_code", "to_currency_code")
    @classmethod
    def normalize_currency_codes(cls, value: str | None) -> str | None:
        return _uppercase_currency(value)

    @model_validator(mode="after")
    def validate_amount(self) -> "TransferCreate":
        if self.from_amount <= 0:
            raise ValueError("Transfer from_amount must be positive")
        if self.to_amount is not None and self.to_amount <= 0:
            raise ValueError("Transfer to_amount must be positive")
        return self


class TransferRead(BaseModel):
    outflow: TransactionRead
    inflow: TransactionRead
    link_id: UUID

    model_config = {"from_attributes": True}
