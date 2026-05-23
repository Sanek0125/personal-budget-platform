import base64
import hashlib
import hmac
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.schemas.auth import AuthLogin, AuthRegister, AuthToken
from app.schemas.user import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUserHeader = Annotated[UUID | None, Header(alias="X-User-Id")]
AuthorizationHeader = Annotated[str | None, Header(alias="Authorization")]
WRITE_ROLES = frozenset({"owner", "admin", "member"})
PASSWORD_HASH_SCHEME = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 210_000
ACCESS_TOKEN_VERSION = "v1"
ACCESS_TOKEN_TTL = timedelta(hours=12)


def _auth_secret() -> bytes:
    return get_settings().auth_secret_key.encode("utf-8")


def _b64_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    salt = secrets.token_urlsafe(24)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    )
    return "$".join(
        [
            PASSWORD_HASH_SCHEME,
            str(PASSWORD_HASH_ITERATIONS),
            salt,
            _b64_encode(digest),
        ]
    )


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        scheme, iterations_raw, salt, expected_digest = password_hash.split("$", 3)
        iterations = int(iterations_raw)
    except ValueError:
        return False
    if scheme != PASSWORD_HASH_SCHEME:
        return False
    actual_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    return hmac.compare_digest(_b64_encode(actual_digest), expected_digest)


def create_access_token(
    user_id: UUID,
    *,
    expires_delta: timedelta = ACCESS_TOKEN_TTL,
) -> str:
    expires_at = datetime.now(UTC) + expires_delta
    payload = {
        "sub": str(user_id),
        "exp": int(expires_at.timestamp()),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    encoded_payload = _b64_encode(payload_bytes)
    signature = hmac.new(
        _auth_secret(),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{ACCESS_TOKEN_VERSION}.{encoded_payload}.{_b64_encode(signature)}"


def _decode_access_token(token: str) -> UUID:
    try:
        version, encoded_payload, encoded_signature = token.split(".", 2)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        ) from exc
    if version != ACCESS_TOKEN_VERSION:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        )
    expected_signature = hmac.new(
        _auth_secret(),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    try:
        actual_signature = _b64_decode(encoded_signature)
        payload = json.loads(_b64_decode(encoded_payload))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        ) from exc
    if not hmac.compare_digest(actual_signature, expected_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        )
    try:
        expires_at = int(payload["exp"])
        user_id = UUID(str(payload["sub"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        ) from exc
    if expires_at < int(datetime.now(UTC).timestamp()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token expired",
        )
    return user_id


def _extract_bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )
    return token.strip()


async def _load_active_user(user_id: UUID, session: AsyncSession) -> User:
    result = await session.execute(
        select(User).where(User.id == user_id, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


async def get_current_user_id(
    authorization: AuthorizationHeader = None,
    x_user_id: CurrentUserHeader = None,
    session: SessionDep = None,  # type: ignore[assignment]
) -> UUID:
    """Identify requester from bearer token, with X-User-Id as explicit dev fallback."""
    token = _extract_bearer_token(authorization)
    if token is None:
        if x_user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        return x_user_id
    user_id = _decode_access_token(token)
    await _load_active_user(user_id, session)
    return user_id


CurrentUserDep = Annotated[UUID, Depends(get_current_user_id)]


async def get_current_user(
    current_user_id: CurrentUserDep,
    session: SessionDep,
) -> User:
    return await _load_active_user(current_user_id, session)


CurrentUserObjectDep = Annotated[User, Depends(get_current_user)]


async def authenticate_user(
    email: str,
    password: str,
    session: AsyncSession,
) -> User:
    result = await session.execute(
        select(User).where(
            User.email == _normalize_email(email),
            User.is_active.is_(True),
        )
    )
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return user


def _token_response(user: User) -> AuthToken:
    return AuthToken(
        access_token=create_access_token(user.id),
        token_type="bearer",
        user=UserRead.model_validate(user),
    )


@router.post("/register", response_model=AuthToken, status_code=status.HTTP_201_CREATED)
async def register(payload: AuthRegister, session: SessionDep) -> AuthToken:
    user = User(
        id=uuid.uuid4(),
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        is_active=True,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=422,
            detail="Unable to register user",
        ) from exc
    await session.refresh(user)
    return _token_response(user)


@router.post("/login", response_model=AuthToken)
async def login(payload: AuthLogin, session: SessionDep) -> AuthToken:
    user = await authenticate_user(payload.email, payload.password, session)
    return _token_response(user)


@router.get("/me", response_model=UserRead)
async def read_current_user(current_user: CurrentUserObjectDep) -> User:
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout() -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def require_workspace_member(
    workspace_id: UUID,
    current_user_id: CurrentUserDep,
    session: SessionDep,
) -> WorkspaceMember:
    result = await session.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user_id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
    return membership


WorkspaceMemberDep = Annotated[WorkspaceMember, Depends(require_workspace_member)]


async def require_workspace_writer(
    workspace_id: UUID,
    current_user_id: CurrentUserDep,
    session: SessionDep,
) -> WorkspaceMember:
    membership = await require_workspace_member(workspace_id, current_user_id, session)
    if membership.role not in WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace write permission required",
        )
    return membership


WorkspaceWriterDep = Annotated[WorkspaceMember, Depends(require_workspace_writer)]
