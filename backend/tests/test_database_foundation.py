from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import get_args, get_origin

from sqlalchemy import CheckConstraint, Index, inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped

from app.db.base import Base
from app.db.seed_data import COMMON_CURRENCIES
from app.models import Currency, ExchangeRate, User, Workspace, WorkspaceMember


def test_database_foundation_models_are_registered_with_metadata() -> None:
    assert User.__tablename__ == "users"
    assert Workspace.__tablename__ == "workspaces"
    assert WorkspaceMember.__tablename__ == "workspace_members"
    assert Currency.__tablename__ == "currencies"
    assert ExchangeRate.__tablename__ == "exchange_rates"

    assert {
        "users",
        "workspaces",
        "workspace_members",
        "currencies",
        "exchange_rates",
    }.issubset(Base.metadata.tables)


def test_users_email_uses_citext_for_case_insensitive_uniqueness() -> None:
    users_table = Base.metadata.tables["users"]

    assert isinstance(users_table.c.email.type, postgresql.CITEXT)
    assert users_table.c.email.unique is True
    assert users_table.c.email.nullable is True


def test_workspace_members_have_unique_workspace_user_pair() -> None:
    table = Base.metadata.tables["workspace_members"]
    unique_constraints = [
        constraint
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    ]

    assert any(
        {column.name for column in constraint.columns} == {"workspace_id", "user_id"}
        for constraint in unique_constraints
    )


def test_exchange_rates_have_unique_rate_identity() -> None:
    table = Base.metadata.tables["exchange_rates"]
    unique_constraints = [
        constraint
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    ]

    assert any(
        {column.name for column in constraint.columns}
        == {"base_currency_code", "quote_currency_code", "rate_date", "source"}
        for constraint in unique_constraints
    )


def test_seed_currency_set_contains_mvp_currencies() -> None:
    codes = {currency.code for currency in COMMON_CURRENCIES}

    assert {"RUB", "USD", "EUR", "GEL", "KZT", "TRY", "AED"}.issubset(codes)
    assert all(len(currency.code) == 3 for currency in COMMON_CURRENCIES)


def test_model_relationships_are_configured() -> None:
    user_relationships = {rel.key for rel in inspect(User).relationships}
    workspace_relationships = {rel.key for rel in inspect(Workspace).relationships}

    assert {"owned_workspaces", "workspace_memberships"}.issubset(user_relationships)
    assert {"owner", "members", "currency"}.issubset(workspace_relationships)


def test_flexible_enum_fields_have_database_check_constraints() -> None:
    workspace_constraints = {
        constraint.name
        for constraint in Base.metadata.tables["workspaces"].constraints
        if isinstance(constraint, CheckConstraint)
    }
    member_constraints = {
        constraint.name
        for constraint in Base.metadata.tables["workspace_members"].constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "ck_workspaces_kind" in workspace_constraints
    assert "ck_workspace_members_role" in member_constraints


def test_model_defaults_match_database_server_defaults() -> None:
    currencies_table = Base.metadata.tables["currencies"]
    users_table = Base.metadata.tables["users"]
    workspaces_table = Base.metadata.tables["workspaces"]
    workspace_members_table = Base.metadata.tables["workspace_members"]
    exchange_rates_table = Base.metadata.tables["exchange_rates"]

    assert currencies_table.c.minor_units.server_default is not None
    assert users_table.c.is_active.server_default is not None
    assert users_table.c.id.server_default is not None
    assert workspaces_table.c.id.server_default is not None
    assert workspace_members_table.c.id.server_default is not None
    assert exchange_rates_table.c.id.server_default is not None


def test_exchange_rate_python_types_match_database_column_types() -> None:
    rate_annotations = ExchangeRate.__annotations__

    assert get_args(rate_annotations["rate"])[0] is Decimal
    assert get_args(rate_annotations["rate_date"])[0] is date

    rate = ExchangeRate(
        base_currency_code="USD",
        quote_currency_code="RUB",
        rate=Decimal("90.000000000000"),
        rate_date=date(2026, 5, 21),
        source="manual",
    )

    assert rate.rate == Decimal("90.000000000000")
    assert rate.rate_date == date(2026, 5, 21)


def test_fk_columns_have_query_indexes() -> None:
    expected_indexes = {
        "workspaces": {"ix_workspaces_owner_user_id": ("owner_user_id",)},
        "workspace_members": {
            "ix_workspace_members_user_id": ("user_id",),
            "ix_workspace_members_workspace_id": ("workspace_id",),
        },
        "exchange_rates": {"ix_exchange_rates_rate_date": ("rate_date",)},
    }

    for table_name, indexes in expected_indexes.items():
        table = Base.metadata.tables[table_name]
        actual = {
            index.name: tuple(column.name for column in index.columns)
            for index in table.indexes
            if isinstance(index, Index)
        }

        for index_name, columns in indexes.items():
            assert actual[index_name] == columns


def test_direct_sql_deletes_match_orm_cascade_intent() -> None:
    expected_ondelete = {
        ("workspaces", "owner_user_id"): "CASCADE",
        ("workspace_members", "workspace_id"): "CASCADE",
        ("workspace_members", "user_id"): "CASCADE",
    }

    for (table_name, column_name), expected in expected_ondelete.items():
        column = Base.metadata.tables[table_name].c[column_name]
        assert next(iter(column.foreign_keys)).ondelete == expected


def test_workspace_member_tracks_role_updates() -> None:
    table = Base.metadata.tables["workspace_members"]

    assert "updated_at" in table.c
    assert table.c.updated_at.server_default is not None


def test_user_display_name_rejects_blank_values() -> None:
    constraint_names = {
        constraint.name
        for constraint in Base.metadata.tables["users"].constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "ck_users_display_name_not_blank" in constraint_names


def test_relationship_annotations_are_typed_with_mapped() -> None:
    relationship_annotations = {
        Workspace: ["owner", "currency", "members"],
        WorkspaceMember: ["workspace", "user"],
        ExchangeRate: ["base_currency", "quote_currency"],
    }

    for model, relationship_names in relationship_annotations.items():
        for relationship_name in relationship_names:
            assert get_origin(model.__annotations__[relationship_name]) is Mapped


def test_migration_reuses_common_currency_seed_data() -> None:
    migration_path = Path("alembic/versions/20260521_0001_database_foundation.py")
    migration = migration_path.read_text()

    assert "from app.db.seed_data import COMMON_CURRENCIES" in migration
    assert "for currency in COMMON_CURRENCIES" in migration
    assert "Russian Ruble" not in migration
