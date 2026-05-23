from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return f"{value:.6f}"
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


def audit_snapshot(obj: object, fields: list[str]) -> dict[str, Any]:
    """Serialize selected ORM object fields into stable JSON audit payloads."""
    return {field: _json_value(getattr(obj, field)) for field in fields}


class _HasId(Protocol):
    id: UUID | None


def ensure_audit_entity_id(obj: _HasId) -> UUID:
    """Return an ORM object's id, assigning the Python UUID default before flush."""
    if obj.id is None:
        obj.id = uuid4()
    return obj.id


def record_audit_event(
    session: AsyncSession,
    *,
    workspace_id: UUID | None,
    user_id: UUID | None,
    entity_type: str,
    entity_id: UUID,
    action: str,
    old_data: dict[str, Any] | None = None,
    new_data: dict[str, Any] | None = None,
) -> AuditLog:
    """Add an audit entry to the current unit of work without committing it."""
    entry = AuditLog(
        workspace_id=workspace_id,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        old_data=_json_value(old_data),
        new_data=_json_value(new_data),
    )
    session.add(entry)
    return entry
