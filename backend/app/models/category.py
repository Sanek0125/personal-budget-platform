import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.workspace import Workspace


class Category(Base):
    """Workspace-scoped category with optional parent for hierarchy."""

    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint(
            "type in ('expense', 'income', 'transfer', 'mixed')",
            name="ck_categories_type",
        ),
        UniqueConstraint(
            "workspace_id",
            "parent_id",
            "name",
            name="uq_categories_workspace_parent_name",
        ),
        Index("ix_categories_workspace_id", "workspace_id"),
        Index("ix_categories_parent_id", "parent_id"),
        Index(
            "uq_categories_workspace_root_name",
            "workspace_id",
            "name",
            unique=True,
            postgresql_where=text("parent_id IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text)
    color: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    workspace: Mapped["Workspace"] = relationship()
    parent: Mapped["Category | None"] = relationship(remote_side=[id])
