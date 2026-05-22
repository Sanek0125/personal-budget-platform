from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.services.category_rules import validate_rule_definition

CategoryRuleOperator = Literal[
    "contains", "equals", "starts_with", "regex", "amount_between"
]
CategoryRuleMatchField = Literal["description", "merchant_name", "merchant_raw"]
MoneyAmount = Annotated[Decimal, Field(max_digits=20, decimal_places=6)]


class CategoryRuleCreate(BaseModel):
    name: str = Field(min_length=1)
    category_id: UUID
    operator: CategoryRuleOperator
    match_field: CategoryRuleMatchField = "description"
    pattern: str | None = None
    amount_min: MoneyAmount | None = None
    amount_max: MoneyAmount | None = None
    priority: int = Field(default=100, ge=0)
    is_active: bool = True

    @model_validator(mode="after")
    def _validate_definition(self) -> "CategoryRuleCreate":
        validate_rule_definition(
            self.operator, self.pattern, self.amount_min, self.amount_max
        )
        return self


class CategoryRuleUpdate(BaseModel):
    """Partial update; cross-field validity is checked against the merged rule."""

    name: str | None = Field(default=None, min_length=1)
    operator: CategoryRuleOperator | None = None
    match_field: CategoryRuleMatchField | None = None
    pattern: str | None = None
    amount_min: MoneyAmount | None = None
    amount_max: MoneyAmount | None = None
    priority: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class CategoryRuleRead(BaseModel):
    id: UUID
    workspace_id: UUID
    category_id: UUID
    name: str
    operator: CategoryRuleOperator
    match_field: CategoryRuleMatchField
    pattern: str | None = None
    amount_min: MoneyAmount | None = None
    amount_max: MoneyAmount | None = None
    priority: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CategoryRuleApplyResult(BaseModel):
    """Outcome of running active rules over a workspace's uncategorized rows."""

    evaluated_count: int
    categorized_count: int
    transaction_ids: list[UUID]
