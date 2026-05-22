"""debts

Revision ID: 20260521_0007
Revises: 20260521_0006
Create Date: 2026-05-21 00:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260521_0007"
down_revision: str | None = "20260521_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contacts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
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
    )
    op.create_index(
        "ix_contacts_workspace_display_name",
        "contacts",
        ["workspace_id", "display_name"],
    )

    op.create_table(
        "debts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("principal_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "source_transaction_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["currency_code"], ["currencies.code"]),
        sa.ForeignKeyConstraint(
            ["source_transaction_id"], ["transactions.id"], ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "direction in ('they_owe_me', 'i_owe_them')",
            name="ck_debts_direction",
        ),
        sa.CheckConstraint(
            "status in ('open', 'partially_paid', 'paid', 'cancelled')",
            name="ck_debts_status",
        ),
        sa.CheckConstraint(
            "principal_amount > 0", name="ck_debts_principal_amount_positive"
        ),
    )
    op.create_index("ix_debts_workspace_status", "debts", ["workspace_id", "status"])
    op.create_index("ix_debts_contact_id", "debts", ["contact_id"])
    op.create_index(
        "ix_debts_source_transaction_id", "debts", ["source_transaction_id"]
    )

    op.create_table(
        "debt_payments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("debt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column(
            "paid_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["debt_id"], ["debts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["currency_code"], ["currencies.code"]),
        sa.ForeignKeyConstraint(
            ["transaction_id"], ["transactions.id"], ondelete="SET NULL"
        ),
        sa.CheckConstraint("amount > 0", name="ck_debt_payments_amount_positive"),
    )
    op.create_index("ix_debt_payments_debt_id", "debt_payments", ["debt_id"])
    op.create_index(
        "ix_debt_payments_transaction_id", "debt_payments", ["transaction_id"]
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_debt_payments_transaction_id")
    op.execute("DROP INDEX IF EXISTS ix_debt_payments_debt_id")
    op.drop_table("debt_payments")
    op.execute("DROP INDEX IF EXISTS ix_debts_source_transaction_id")
    op.execute("DROP INDEX IF EXISTS ix_debts_contact_id")
    op.execute("DROP INDEX IF EXISTS ix_debts_workspace_status")
    op.drop_table("debts")
    op.execute("DROP INDEX IF EXISTS ix_contacts_workspace_display_name")
    op.drop_table("contacts")
