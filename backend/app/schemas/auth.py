from pydantic import BaseModel, Field, field_validator

from app.schemas.user import UserRead


class AuthRegister(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(min_length=8, max_length=1024)
    display_name: str = Field(min_length=1)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("Email must be a string")
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("Email must not be blank")
        return normalized

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Display name must not be blank")
        return trimmed


class AuthLogin(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("Email must be a string")
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("Email must not be blank")
        return normalized


class AuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
