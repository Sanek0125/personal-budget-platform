from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

DebtDirection = Literal["they_owe_me", "i_owe_them"]
DebtStatus = Literal["open", "partially_paid", "paid", "cancelled"]
MoneyAmount = Annotated[Decimal, Field(max_digits=20, decimal_places=6)]


def _uppercase_currency(value: str) -> str:
    return value.upper()


class DebtCreate(BaseModel):
    contact_id: UUID | None = None
    contact_name: str | None = Field(default=None, min_length=1)
    direction: DebtDirection
    principal_amount: MoneyAmount = Field(gt=0)
    currency_code: str = Field(min_length=3, max_length=3)
    description: str = Field(min_length=1)
    due_date: date | None = None
    source_transaction_id: UUID | None = None

    @field_validator("currency_code")
    @classmethod
    def normalize_currency_code(cls, value: str) -> str:
        return _uppercase_currency(value)

    @model_validator(mode="after")
    def require_contact_reference(self) -> "DebtCreate":
        if self.contact_id is None and self.contact_name is None:
            raise ValueError("Either contact_id or contact_name is required")
        if self.contact_id is not None and self.contact_name is not None:
            raise ValueError("Provide contact_id or contact_name, not both")
        return self


class ContactRead(BaseModel):
    id: UUID
    workspace_id: UUID
    display_name: str
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class DebtPaymentCreate(BaseModel):
    amount: MoneyAmount = Field(gt=0)
    currency_code: str = Field(min_length=3, max_length=3)
    paid_at: datetime | None = None
    notes: str | None = None
    transaction_id: UUID | None = None

    @field_validator("currency_code")
    @classmethod
    def normalize_currency_code(cls, value: str) -> str:
        return _uppercase_currency(value)


class DebtPaymentRead(BaseModel):
    id: UUID
    debt_id: UUID
    amount: MoneyAmount
    currency_code: str
    paid_at: datetime | None = None
    notes: str | None = None
    transaction_id: UUID | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class DebtRead(BaseModel):
    id: UUID
    workspace_id: UUID
    contact_id: UUID
    direction: DebtDirection
    status: DebtStatus
    principal_amount: MoneyAmount
    currency_code: str
    description: str
    due_date: date | None = None
    source_transaction_id: UUID | None = None
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    payments: list[DebtPaymentRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class DebtSummaryTotal(BaseModel):
    direction: DebtDirection
    currency_code: str
    principal_amount: MoneyAmount
    paid_amount: MoneyAmount
    remaining_amount: MoneyAmount


class DebtSummaryRead(BaseModel):
    workspace_id: UUID | None = None
    totals: list[DebtSummaryTotal]
