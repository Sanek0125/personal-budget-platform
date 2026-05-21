from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, SmallInteger, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.exchange_rate import ExchangeRate
    from app.models.workspace import Workspace


class Currency(Base):
    """ISO-4217 currency reference data."""

    __tablename__ = "currencies"
    __table_args__ = (
        CheckConstraint("char_length(code) = 3", name="ck_currencies_code_len"),
        CheckConstraint(
            "minor_units >= 0",
            name="ck_currencies_minor_units_non_negative",
        ),
    )

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    symbol: Mapped[str | None] = mapped_column(Text, nullable=True)
    minor_units: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=2,
        server_default=text("2"),
    )

    workspaces: Mapped[list["Workspace"]] = relationship(back_populates="currency")
    base_exchange_rates: Mapped[list["ExchangeRate"]] = relationship(
        back_populates="base_currency",
        foreign_keys="ExchangeRate.base_currency_code",
    )
    quote_exchange_rates: Mapped[list["ExchangeRate"]] = relationship(
        back_populates="quote_currency",
        foreign_keys="ExchangeRate.quote_currency_code",
    )
