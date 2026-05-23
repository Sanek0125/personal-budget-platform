from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

WorkspaceKind = Literal["personal", "family", "trip", "other"]
WorkspaceRole = Literal["owner", "admin", "member", "viewer"]
WorkspaceAssignableRole = Literal["admin", "member", "viewer"]


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1)
    kind: WorkspaceKind
    base_currency_code: str = Field(min_length=3, max_length=3)
    owner_user_id: UUID

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Workspace name must not be blank")
        return trimmed

    @field_validator("base_currency_code", mode="before")
    @classmethod
    def normalize_currency_code(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("Currency code must be a string")
        return value.strip().upper()


class WorkspaceRead(BaseModel):
    id: UUID
    name: str
    kind: WorkspaceKind
    base_currency_code: str
    owner_user_id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class WorkspaceMemberCreate(BaseModel):
    user_id: UUID
    role: WorkspaceAssignableRole


class WorkspaceMemberRead(BaseModel):
    id: UUID
    workspace_id: UUID
    user_id: UUID
    role: WorkspaceRole
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
