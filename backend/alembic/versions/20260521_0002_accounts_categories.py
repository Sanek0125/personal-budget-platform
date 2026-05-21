"""accounts and categories

Revision ID: 20260521_0002
Revises: 20260521_0001
Create Date: 2026-05-21 00:00:00+00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260521_0002"
down_revision: str | None = "20260521_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("institution_name", sa.Text(), nullable=True),
        sa.Column("masked_number", sa.Text(), nullable=True),
        sa.Column(
            "opening_balance",
            sa.Numeric(20, 6),
            nullable=False,
            server_default="0",
        ),
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
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["currency_code"], ["currencies.code"]),
        sa.CheckConstraint(
            "type in ("
            "'bank_card', 'cash', 'bank_account', 'bonus', "
            "'investment', 'crypto', 'other'"
            ")",
            name="ck_accounts_type",
        ),
    )
    op.create_index("ix_accounts_workspace_id", "accounts", ["workspace_id"])
    op.create_index("ix_accounts_owner_user_id", "accounts", ["owner_user_id"])

    op.create_table(
        "categories",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("color", sa.Text(), nullable=True),
        sa.Column("icon", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
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
        sa.ForeignKeyConstraint(
            ["parent_id"], ["categories.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "parent_id",
            "name",
            name="uq_categories_workspace_parent_name",
        ),
        sa.CheckConstraint(
            "type in ('expense', 'income', 'transfer', 'mixed')",
            name="ck_categories_type",
        ),
    )
    op.create_index("ix_categories_workspace_id", "categories", ["workspace_id"])
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"])
    op.create_index(
        "uq_categories_workspace_root_name",
        "categories",
        ["workspace_id", "name"],
        unique=True,
        postgresql_where=sa.text("parent_id IS NULL"),
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_categories_workspace_root_name")
    op.execute("DROP INDEX IF EXISTS ix_categories_parent_id")
    op.execute("DROP INDEX IF EXISTS ix_categories_workspace_id")
    op.execute("DROP INDEX IF EXISTS ix_accounts_owner_user_id")
    op.execute("DROP INDEX IF EXISTS ix_accounts_workspace_id")
    op.drop_table("categories")
    op.drop_table("accounts")
