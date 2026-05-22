from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

RewardProgramType = Literal["cashback", "points", "miles"]
RewardEventType = Literal["earned", "redeemed", "adjusted", "expired"]
RewardEventStatus = Literal["expected", "posted", "cancelled"]
RewardKind = Literal["cashback", "points", "miles"]
MoneyAmount = Annotated[Decimal, Field(max_digits=20, decimal_places=6)]


def _uppercase_currency(value: str | None) -> str | None:
    return value.upper() if value is not None else None


class RewardProgramCreate(BaseModel):
    name: str = Field(min_length=1)
    program_type: RewardProgramType
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    issuer_name: str | None = None
    is_active: bool = True
    notes: str | None = None

    @field_validator("currency_code")
    @classmethod
    def normalize_currency_code(cls, value: str | None) -> str | None:
        return _uppercase_currency(value)

    @model_validator(mode="after")
    def validate_currency_for_type(self) -> "RewardProgramCreate":
        if self.program_type == "cashback" and self.currency_code is None:
            raise ValueError("Cashback programs require currency_code")
        if self.program_type in {"points", "miles"} and self.currency_code is not None:
            raise ValueError("Points and miles programs must not set currency_code")
        return self


class RewardProgramRead(BaseModel):
    id: UUID
    workspace_id: UUID
    name: str
    program_type: RewardProgramType
    currency_code: str | None
    issuer_name: str | None = None
    is_active: bool
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class CashbackRuleCreate(BaseModel):
    program_id: UUID
    name: str = Field(min_length=1)
    rate: MoneyAmount = Field(gt=0)
    spend_currency_code: str = Field(min_length=3, max_length=3)
    category_id: UUID | None = None
    merchant_pattern: str | None = None
    min_spend_amount: MoneyAmount | None = Field(default=None, gt=0)
    max_reward_amount: MoneyAmount | None = Field(default=None, gt=0)
    priority: int = 100
    is_active: bool = True

    @field_validator("spend_currency_code")
    @classmethod
    def normalize_spend_currency_code(cls, value: str) -> str:
        return value.upper()


class CashbackRuleRead(BaseModel):
    id: UUID
    workspace_id: UUID
    program_id: UUID
    name: str
    rate: MoneyAmount
    spend_currency_code: str
    category_id: UUID | None
    merchant_pattern: str | None
    min_spend_amount: MoneyAmount | None
    max_reward_amount: MoneyAmount | None
    priority: int
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class RewardEventCreate(BaseModel):
    program_id: UUID
    event_type: RewardEventType
    status: RewardEventStatus = "posted"
    reward_kind: RewardKind
    amount: MoneyAmount = Field(gt=0)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    occurred_at: datetime
    description: str | None = None
    notes: str | None = None
    cashback_rule_id: UUID | None = None
    source_transaction_id: UUID | None = None
    reward_transaction_id: UUID | None = None

    @field_validator("currency_code")
    @classmethod
    def normalize_currency_code(cls, value: str | None) -> str | None:
        return _uppercase_currency(value)

    @model_validator(mode="after")
    def validate_currency_for_kind(self) -> "RewardEventCreate":
        if self.reward_kind == "cashback" and self.currency_code is None:
            raise ValueError("Cashback reward events require currency_code")
        if self.reward_kind in {"points", "miles"} and self.currency_code is not None:
            raise ValueError(
                "Points and miles reward events must not set currency_code"
            )
        return self


class RewardEventRead(BaseModel):
    id: UUID
    workspace_id: UUID
    program_id: UUID
    cashback_rule_id: UUID | None
    source_transaction_id: UUID | None
    reward_transaction_id: UUID | None
    event_type: RewardEventType
    status: RewardEventStatus
    reward_kind: RewardKind
    amount: MoneyAmount
    currency_code: str | None
    occurred_at: datetime
    description: str
    notes: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ExpectedRewardRequest(BaseModel):
    program_id: UUID
    source_transaction_id: UUID


class ExpectedRewardRead(BaseModel):
    program_id: UUID
    rule_id: UUID
    source_transaction_id: UUID
    reward_kind: RewardKind
    amount: MoneyAmount
    currency_code: str | None
    description: str
