"""database foundation

Revision ID: 20260521_0001
Revises:
Create Date: 2026-05-21 00:00:00+00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.db.seed_data import COMMON_CURRENCIES

revision: str = "20260521_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    currencies = op.create_table(
        "currencies",
        sa.Column("code", sa.String(length=3), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=True),
        sa.Column("minor_units", sa.SmallInteger(), nullable=False, server_default="2"),
        sa.CheckConstraint("char_length(code) = 3", name="ck_currencies_code_len"),
        sa.CheckConstraint(
            "minor_units >= 0", name="ck_currencies_minor_units_non_negative"
        ),
    )

    op.bulk_insert(
        currencies,
        [
            {
                "code": currency.code,
                "name": currency.name,
                "symbol": currency.symbol,
                "minor_units": currency.minor_units,
            }
            for currency in COMMON_CURRENCIES
        ],
    )

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", postgresql.CITEXT(), nullable=True, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=True, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "btrim(display_name) != ''",
            name="ck_users_display_name_not_blank",
        ),
    )

    op.create_table(
        "workspaces",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("base_currency_code", sa.String(length=3), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["base_currency_code"], ["currencies.code"]),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "kind in ('personal', 'family', 'trip', 'other')",
            name="ck_workspaces_kind",
        ),
    )
    op.create_index(
        "ix_workspaces_owner_user_id", "workspaces", ["owner_user_id"]
    )

    op.create_table(
        "workspace_members",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "workspace_id", "user_id", name="uq_workspace_members_workspace_user"
        ),
        sa.CheckConstraint(
            "role in ('owner', 'admin', 'member', 'viewer')",
            name="ck_workspace_members_role",
        ),
    )
    op.create_index(
        "ix_workspace_members_user_id", "workspace_members", ["user_id"]
    )
    op.create_index(
        "ix_workspace_members_workspace_id", "workspace_members", ["workspace_id"]
    )

    op.create_table(
        "exchange_rates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("base_currency_code", sa.String(length=3), nullable=False),
        sa.Column("quote_currency_code", sa.String(length=3), nullable=False),
        sa.Column("rate", sa.Numeric(24, 12), nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("rate > 0", name="ck_exchange_rates_rate_positive"),
        sa.ForeignKeyConstraint(["base_currency_code"], ["currencies.code"]),
        sa.ForeignKeyConstraint(["quote_currency_code"], ["currencies.code"]),
        sa.UniqueConstraint(
            "base_currency_code",
            "quote_currency_code",
            "rate_date",
            "source",
            name="uq_exchange_rates_identity",
        ),
    )
    op.create_index("ix_exchange_rates_rate_date", "exchange_rates", ["rate_date"])


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_exchange_rates_rate_date")
    op.execute("DROP INDEX IF EXISTS ix_workspace_members_workspace_id")
    op.execute("DROP INDEX IF EXISTS ix_workspace_members_user_id")
    op.execute("DROP INDEX IF EXISTS ix_workspaces_owner_user_id")
    op.drop_table("exchange_rates")
    op.drop_table("workspace_members")
    op.drop_table("workspaces")
    op.drop_table("users")
    op.drop_table("currencies")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
    op.execute("DROP EXTENSION IF EXISTS citext")
