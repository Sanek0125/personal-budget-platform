from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

BudgetPeriodType = Literal["monthly"]
MoneyAmount = Annotated[Decimal, Field(max_digits=20, decimal_places=6)]


def _uppercase_currency(value: str) -> str:
    return value.upper()


class BudgetCreate(BaseModel):
    name: str = Field(min_length=1)
    period_type: BudgetPeriodType = "monthly"
    period_start: date
    period_end: date
    currency_code: str = Field(min_length=3, max_length=3)
    is_active: bool = True

    @field_validator("currency_code")
    @classmethod
    def normalize_currency_code(cls, value: str) -> str:
        return _uppercase_currency(value)

    @model_validator(mode="after")
    def validate_period_dates(self) -> "BudgetCreate":
        if self.period_end < self.period_start:
            raise ValueError("Budget period_end must be on or after period_start")
        return self


class BudgetRead(BaseModel):
    id: UUID
    workspace_id: UUID
    name: str
    period_type: BudgetPeriodType
    period_start: date
    period_end: date
    currency_code: str
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class BudgetLimitCreate(BaseModel):
    category_id: UUID
    amount: MoneyAmount = Field(gt=0)
    currency_code: str = Field(min_length=3, max_length=3)
    rollover: bool = False

    @field_validator("currency_code")
    @classmethod
    def normalize_currency_code(cls, value: str) -> str:
        return _uppercase_currency(value)


class BudgetLimitRead(BaseModel):
    id: UUID
    budget_id: UUID
    category_id: UUID
    amount: MoneyAmount
    currency_code: str
    rollover: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class BudgetLimitProgress(BaseModel):
    category_id: UUID
    limit_amount: MoneyAmount
    spent_amount: MoneyAmount
    remaining_amount: MoneyAmount
    percent_used: Decimal
    currency_code: str


class BudgetProgressRead(BaseModel):
    budget_id: UUID
    period_start: date
    period_end: date
    currency_code: str
    total_limit: MoneyAmount
    total_spent: MoneyAmount
    total_remaining: MoneyAmount
    limits: list[BudgetLimitProgress]
