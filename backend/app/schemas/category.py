from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

CategoryType = Literal["expense", "income", "transfer", "mixed"]


class CategoryCreate(BaseModel):
    parent_id: UUID | None = None
    name: str = Field(min_length=1)
    type: CategoryType
    color: str | None = None
    icon: str | None = None
    sort_order: int = 0


class CategoryRead(CategoryCreate):
    id: UUID
    workspace_id: UUID
    is_system: bool

    model_config = {"from_attributes": True}
