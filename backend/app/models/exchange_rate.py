import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ExchangeRate(Base):
    """Exchange-rate quote for a specific date and data source."""

    __tablename__ = "exchange_rates"
    __table_args__ = (
        UniqueConstraint(
            "base_currency_code",
            "quote_currency_code",
            "rate_date",
            "source",
            name="uq_exchange_rates_identity",
        ),
        CheckConstraint("rate > 0", name="ck_exchange_rates_rate_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    base_currency_code: Mapped[str] = mapped_column(
        ForeignKey("currencies.code"), nullable=False
    )
    quote_currency_code: Mapped[str] = mapped_column(
        ForeignKey("currencies.code"), nullable=False
    )
    rate: Mapped[Decimal] = mapped_column(Numeric(24, 12), nullable=False)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    base_currency = relationship(
        "Currency",
        back_populates="base_exchange_rates",
        foreign_keys=[base_currency_code],
    )
    quote_currency = relationship(
        "Currency",
        back_populates="quote_exchange_rates",
        foreign_keys=[quote_currency_code],
    )
