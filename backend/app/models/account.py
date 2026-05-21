import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    func,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.currency import Currency
    from app.models.user import User
    from app.models.workspace import Workspace


class Account(Base):
    """Cash wallet, bank card, bank account, bonus account, or similar asset."""

    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint(
            "type in ("
            "'bank_card', 'cash', 'bank_account', 'bonus', "
            "'investment', 'crypto', 'other'"
            ")",
            name="ck_accounts_type",
        ),
        Index("ix_accounts_workspace_id", "workspace_id"),
        Index("ix_accounts_owner_user_id", "owner_user_id"),
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
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text)
    currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"))
    institution_name: Mapped[str | None] = mapped_column(Text)
    masked_number: Mapped[str | None] = mapped_column(Text)
    opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(20, 6),
        nullable=False,
        default=Decimal("0"),
        server_default=text("0"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
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
    owner: Mapped["User | None"] = relationship()
    currency: Mapped["Currency"] = relationship()
