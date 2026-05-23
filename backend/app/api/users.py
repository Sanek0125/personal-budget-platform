from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.user import User
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/users", tags=["users"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def _normalize_email_filter(email: str | None) -> str | None:
    if email is None:
        return None
    normalized = email.strip().lower()
    return normalized or None


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, session: SessionDep) -> User:
    user = User(
        email=payload.email,
        display_name=payload.display_name,
        telegram_id=payload.telegram_id,
        is_active=True,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=422,
            detail="Unable to create user",
        ) from exc
    await session.refresh(user)
    return user


@router.get("", response_model=list[UserRead])
async def list_users(
    session: SessionDep,
    email: Annotated[str | None, Query()] = None,
) -> list[User]:
    statement = select(User).order_by(User.created_at, User.id)
    normalized_email = _normalize_email_filter(email)
    if normalized_email is not None:
        statement = statement.where(User.email == normalized_email)

    result = await session.execute(statement)
    return list(result.scalars().all())


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: UUID, session: SessionDep) -> User:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user
