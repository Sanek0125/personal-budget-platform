from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import CheckConstraint, Index, UniqueConstraint, inspect
from sqlalchemy.exc import IntegrityError

from app.api.imports import (
    confirm_import_batch,
    get_import_batch,
    list_import_rows,
    upload_csv_import,
)
from app.db.base import Base
from app.models import Account, File, ImportBatch, ImportRow, Transaction
from app.schemas.imports import CsvImportUpload
from app.services.csv_imports import CsvColumnMapping, parse_csv_rows
from app.services.import_parsers import parse_import_rows


class _ScalarResult:
    def __init__(
        self, value: object | None = None, values: list[object] | None = None
    ) -> None:
        self._value = value
        self._values = values or ([] if value is None else [value])

    def scalar_one_or_none(self) -> object | None:
        return self._value

    def scalars(self) -> "_ScalarResult":
        return self

    def all(self) -> list[object]:
        return self._values


class _FakeAsyncSession:
    def __init__(
        self,
        *results: object | list[object] | None,
        commit_exception: Exception | None = None,
    ) -> None:
        self.results = list(results)
        self.commit_exception = commit_exception
        self.added: list[object] = []
        self.added_all: list[object] = []
        self.committed = False
        self.rolled_back = False
        self.flushed = False
        self.refreshed: list[object] = []
        self.statements: list[object] = []

    async def execute(self, statement: object) -> _ScalarResult:
        self.statements.append(statement)
        value = self.results.pop(0) if self.results else None
        if isinstance(value, list):
            return _ScalarResult(values=value)
        return _ScalarResult(value)

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def add_all(self, objects: list[object]) -> None:
        self.added_all.extend(objects)

    async def flush(self) -> None:
        self.flushed = True

    async def commit(self) -> None:
        if self.commit_exception is not None:
            raise self.commit_exception
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def refresh(
        self, obj: object, attribute_names: list[str] | None = None
    ) -> None:
        del attribute_names
        self.refreshed.append(obj)


def _account(workspace_id, account_id=None, currency_code="USD") -> Account:
    return Account(
        id=account_id or uuid4(),
        workspace_id=workspace_id,
        name="Cash",
        type="cash",
        currency_code=currency_code,
    )


def _batch(workspace_id, account_id=None, batch_id=None) -> ImportBatch:
    return ImportBatch(
        id=batch_id or uuid4(),
        workspace_id=workspace_id,
        user_id=uuid4(),
        account_id=account_id or uuid4(),
        source_type="csv",
        original_filename="statement.csv",
        file_hash="hash",
        status="parsed",
        total_rows=1,
    )


def _row(batch: ImportBatch, row_id=None, status="pending") -> ImportRow:
    return ImportRow(
        id=row_id or uuid4(),
        import_batch_id=batch.id,
        workspace_id=batch.workspace_id,
        row_number=1,
        raw_data={"date": "2026-05-21", "amount": "-12.34"},
        normalized_data={
            "type": "expense",
            "occurred_at": "2026-05-21T00:00:00+00:00",
            "amount": "-12.34",
            "currency_code": "USD",
            "description": "Lunch",
            "external_id": "bank-1",
        },
        raw_hash="raw-hash",
        normalized_hash="normalized-hash",
        status=status,
    )


def _pdf_line(*parts: tuple[int, str]) -> str:
    line = ""
    for column, text in parts:
        if len(line) < column:
            line += " " * (column - len(line))
        line += text
    return line


def _freedom_pdf_text_fixture() -> str:
    return "\n".join(
        [
            "Выписка по текущему счету за период с 01.05.2026 по 31.05.2026",
            "Счет: KZ000000000000000KZT",
            "Клиент: Test Client",
            "Валюта: KZT",
            "Выписка по счету KZ000000000000000KZT",
            _pdf_line(
                (43, "бенефициара"),
                (112, "Дебет"),
                (121, "Кредит"),
                (131, "Назначение платежа"),
            ),
            " операции     документа     бенефициара/",
            "",
            _pdf_line((131, "Дата и время")),
            _pdf_line((131, "транзакции: 22.05.2026")),
            _pdf_line((131, "17:13:24, номер карты:")),
            _pdf_line((131, "5269****7519, сумма")),
            _pdf_line((28, 'АО "Фридом'), (131, "транзакции: 200000 KZT,")),
            _pdf_line((60, "общество"), (122, "200")),
            _pdf_line(
                (1, "22.05.2026"),
                (16, "9397251"),
                (31, "Банк"),
                (42, "KSNVKZKA"),
                (87, "KZ000000000000000KZT"),
                (131, "операция: Зачисление на"),
            ),
            _pdf_line((58, "«Фридом Банк"), (121, "000.00")),
            _pdf_line((28, 'Казахстан"'), (131, "счет, место выполнение")),
            _pdf_line((60, "Казахстан»")),
            _pdf_line((131, "P2P_KGDM_Credit>Almaty")),
            _pdf_line((131, "РРН:614212829378")),
            "",
            _pdf_line((28, 'АО "Фридом'), (60, "Test Client")),
            _pdf_line((114, "7")),
            _pdf_line(
                (1, "13.05.2026"),
                (16, "5206342"),
                (31, "Банк"),
                (42, "KSNVKZKA"),
                (60, "Test Client"),
                (73, "000000000000"),
                (87, "KZ000000000000000KZT"),
                (131, "Конвертация"),
            ),
            _pdf_line((112, "405.67")),
            _pdf_line((28, 'Казахстан"'), (60, "Test Client")),
            "",
            "Исходящий остаток: 0.00",
        ]
    )


def test_import_models_are_registered_with_metadata() -> None:
    assert File.__tablename__ == "files"
    assert ImportBatch.__tablename__ == "import_batches"
    assert ImportRow.__tablename__ == "import_rows"
    assert {"files", "import_batches", "import_rows", "duplicate_candidates"}.issubset(
        Base.metadata.tables
    )


def test_import_models_have_expected_constraints_and_indexes() -> None:
    files = Base.metadata.tables["files"]
    batches = Base.metadata.tables["import_batches"]
    rows = Base.metadata.tables["import_rows"]
    duplicate_candidates = Base.metadata.tables["duplicate_candidates"]

    file_uniques = {
        c.name for c in files.constraints if isinstance(c, UniqueConstraint)
    }
    batch_uniques = {
        c.name for c in batches.constraints if isinstance(c, UniqueConstraint)
    }
    row_uniques = {c.name for c in rows.constraints if isinstance(c, UniqueConstraint)}
    batch_checks = {
        c.name for c in batches.constraints if isinstance(c, CheckConstraint)
    }
    row_checks = {c.name for c in rows.constraints if isinstance(c, CheckConstraint)}
    candidate_indexes = {
        i.name for i in duplicate_candidates.indexes if isinstance(i, Index)
    }

    assert "uq_files_workspace_sha256" in file_uniques
    assert "uq_import_batches_workspace_file_hash" in batch_uniques
    assert {"uq_import_rows_batch_row_number"}.issubset(row_uniques)
    assert "uq_import_rows_batch_raw_hash" not in row_uniques
    assert {"ck_import_batches_source_type", "ck_import_batches_status"}.issubset(
        batch_checks
    )
    assert "ck_import_rows_status" in row_checks
    assert "ix_duplicate_candidates_workspace_id" in candidate_indexes


def test_import_relationship_annotations_are_configured() -> None:
    batch_relationships = {rel.key for rel in inspect(ImportBatch).relationships}
    row_relationships = {rel.key for rel in inspect(ImportRow).relationships}

    assert {"workspace", "user", "account", "file", "rows"}.issubset(
        batch_relationships
    )
    assert {"batch", "transaction"}.issubset(row_relationships)


def test_parse_csv_rows_normalizes_rows_and_hashes() -> None:
    csv_content = (
        "Date,Amount,Currency,Description,External ID\n"
        "2026-05-21,-12.34,usd,Lunch,bank-1\n"
    )
    rows = parse_csv_rows(
        csv_content,
        CsvColumnMapping(
            occurred_at="Date",
            amount="Amount",
            currency_code="Currency",
            description="Description",
            external_id="External ID",
        ),
    )

    assert len(rows) == 1
    assert rows[0].row_number == 1
    assert rows[0].raw_data["Date"] == "2026-05-21"
    assert rows[0].normalized_data["type"] == "expense"
    assert rows[0].normalized_data["currency_code"] == "USD"
    assert rows[0].normalized_data["amount"] == "-12.34"
    assert rows[0].raw_hash
    assert rows[0].normalized_hash


def test_parse_freedom_rows_normalizes_semicolon_statement() -> None:
    content = (
        "Дата операции;Дата обработки;Описание;Сумма;Валюта;ID операции\n"
        "23.05.2026 14:35;24.05.2026;MAGNUM;−1 234,56;KZT;freedom-1\n"
    )

    rows = parse_import_rows(content, parser_name="freedom", column_mapping=None)

    assert len(rows) == 1
    assert rows[0].row_number == 1
    assert rows[0].raw_data["Описание"] == "MAGNUM"
    assert rows[0].normalized_data == {
        "type": "expense",
        "occurred_at": "2026-05-23T14:35:00+00:00",
        "amount": "-1234.56",
        "currency_code": "KZT",
        "description": "MAGNUM",
        "booked_at": "2026-05-24T00:00:00+00:00",
        "merchant_raw": "MAGNUM",
        "external_id": "freedom-1",
    }
    assert rows[0].raw_hash
    assert rows[0].normalized_hash


def test_parse_freedom_rows_uses_debit_credit_columns() -> None:
    content = (
        "Date,Description,Debit,Credit,Currency,Transaction ID\n"
        "2026-05-23,Salary,,5000.00,USD,income-1\n"
        "2026-05-24,Coffee,4.50,,USD,expense-1\n"
    )

    rows = parse_import_rows(content, parser_name="freedom", column_mapping=None)

    assert rows[0].normalized_data["type"] == "income"
    assert rows[0].normalized_data["amount"] == "5000.00"
    assert rows[1].normalized_data["type"] == "expense"
    assert rows[1].normalized_data["amount"] == "-4.50"


def test_parse_freedom_pdf_text_statement_extracts_wrapped_debit_credit_rows() -> None:
    rows = parse_import_rows(
        _freedom_pdf_text_fixture(), parser_name="freedom", column_mapping=None
    )

    assert len(rows) == 2
    assert rows[0].raw_data["document_number"] == "9397251"
    assert rows[0].normalized_data["type"] == "income"
    assert rows[0].normalized_data["occurred_at"] == "2026-05-22T17:13:24+00:00"
    assert rows[0].normalized_data["amount"] == "200000.00"
    assert rows[0].normalized_data["currency_code"] == "KZT"
    assert rows[0].normalized_data["external_id"] == "614212829378"
    assert "Зачисление на счет" in rows[0].normalized_data["description"]
    assert rows[1].raw_data["document_number"] == "5206342"
    assert rows[1].normalized_data["type"] == "expense"
    assert rows[1].normalized_data["amount"] == "-7405.67"
    assert rows[1].normalized_data["description"] == "Конвертация"


async def test_upload_freedom_import_creates_file_batch_and_rows_without_mapping(
) -> None:
    workspace_id = uuid4()
    account = _account(workspace_id)
    user_id = uuid4()
    session = _FakeAsyncSession(workspace_id, account, user_id)

    batch = await upload_csv_import(
        workspace_id,
        CsvImportUpload(
            user_id=user_id,
            account_id=account.id,
            original_filename="freedom.pdf",
            content=_freedom_pdf_text_fixture(),
            parser_name="freedom",
            source_name="Freedom Bank",
        ),
        session,  # type: ignore[arg-type]
    )

    files = [obj for obj in session.added_all if isinstance(obj, File)]
    rows = [obj for obj in session.added_all if isinstance(obj, ImportRow)]
    assert batch.parser_version == "freedom-v1"
    assert batch.source_name == "Freedom Bank"
    assert batch.source_type == "pdf"
    assert files[0].content_type == "application/pdf+text"
    assert batch.total_rows == 2
    assert rows[1].normalized_data["description"] == "Конвертация"
    assert rows[1].normalized_data["amount"] == "-7405.67"


async def test_upload_csv_import_creates_file_batch_and_rows() -> None:
    workspace_id = uuid4()
    account = _account(workspace_id)
    user_id = uuid4()
    session = _FakeAsyncSession(workspace_id, account, user_id)

    batch = await upload_csv_import(
        workspace_id,
        CsvImportUpload(
            user_id=user_id,
            account_id=account.id,
            original_filename="statement.csv",
            content="Date,Amount,Currency,Description\n2026-05-21,-12.34,usd,Lunch\n",
            column_mapping=CsvColumnMapping(
                occurred_at="Date",
                amount="Amount",
                currency_code="Currency",
                description="Description",
            ),
        ),
        session,  # type: ignore[arg-type]
    )

    assert session.flushed is True
    assert session.committed is True
    assert batch.workspace_id == workspace_id
    assert batch.status == "parsed"
    assert batch.total_rows == 1
    assert len(session.added_all) == 3
    assert any(isinstance(row, ImportRow) for row in session.added_all)


async def test_upload_csv_import_rolls_back_integrity_errors() -> None:
    workspace_id = uuid4()
    account = _account(workspace_id)
    user_id = uuid4()
    session = _FakeAsyncSession(
        workspace_id,
        account,
        user_id,
        commit_exception=IntegrityError("statement", "params", Exception("uq")),
    )

    try:
        await upload_csv_import(
            workspace_id,
            CsvImportUpload(
                user_id=user_id,
                account_id=account.id,
                original_filename="statement.csv",
                content="Date,Amount,Currency,Description\n2026-05-21,-12.34,usd,Lunch\n",
                column_mapping=CsvColumnMapping(
                    occurred_at="Date",
                    amount="Amount",
                    currency_code="Currency",
                    description="Description",
                ),
            ),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 409
        assert session.rolled_back is True
    else:
        raise AssertionError("duplicate import should be translated")


async def test_preview_endpoints_return_batch_and_rows() -> None:
    workspace_id = uuid4()
    batch = _batch(workspace_id)
    row = _row(batch)
    session = _FakeAsyncSession(batch, batch, [row])

    assert await get_import_batch(workspace_id, batch.id, session) == batch  # type: ignore[arg-type]
    assert await list_import_rows(workspace_id, batch.id, session) == [row]  # type: ignore[arg-type]


async def test_confirm_import_batch_creates_transactions_and_marks_duplicates() -> None:
    workspace_id = uuid4()
    account = _account(workspace_id)
    batch = _batch(workspace_id, account.id)
    import_row = _row(batch)
    duplicate_row = _row(batch, status="pending")
    existing = Transaction(
        id=uuid4(),
        workspace_id=workspace_id,
        account_id=account.id,
        type="expense",
        status="posted",
        occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
        amount=Decimal("-12.34"),
        currency_code="USD",
        description="Lunch",
        source="csv_import",
        fingerprint="fp",
    )
    session = _FakeAsyncSession(
        batch, [import_row, duplicate_row], account, None, existing
    )

    result = await confirm_import_batch(workspace_id, batch.id, session)  # type: ignore[arg-type]

    assert result.imported_count == 1
    assert result.duplicate_count == 1
    assert batch.status == "processed"
    assert import_row.status == "imported"
    assert duplicate_row.status == "duplicate"
    assert isinstance(import_row.transaction_id, type(result.transaction_ids[0]))
    assert any(isinstance(obj, Transaction) for obj in session.added)
    assert session.committed is True
