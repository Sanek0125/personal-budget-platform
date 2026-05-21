from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

AccountType = Literal[
    "bank_card",
    "cash",
    "bank_account",
    "bonus",
    "investment",
    "crypto",
    "other",
]


class AccountCreate(BaseModel):
    owner_user_id: UUID | None = None
    name: str = Field(min_length=1)
    type: AccountType
    currency_code: str = Field(min_length=3, max_length=3)
    institution_name: str | None = None
    masked_number: str | None = None
    opening_balance: Decimal = Decimal("0")

    @field_validator("currency_code")
    @classmethod
    def normalize_currency_code(cls, value: str) -> str:
        return value.upper()


class AccountRead(AccountCreate):
    id: UUID
    workspace_id: UUID
    is_active: bool

    model_config = {"from_attributes": True}
