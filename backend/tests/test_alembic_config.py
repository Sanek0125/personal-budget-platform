import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_alembic_has_single_head_revision() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=BACKEND_DIR,
        check=True,
        capture_output=True,
        text=True,
    )

    heads = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(heads) == 1
    assert "20260521_0007" in heads[0]


def test_alembic_migration_references_common_currency_seed_data() -> None:
    versions_dir = BACKEND_DIR / "alembic" / "versions"
    migration_text = "\n".join(path.read_text() for path in versions_dir.glob("*.py"))
    seed_data_text = (BACKEND_DIR / "app" / "db" / "seed_data.py").read_text()

    assert "from app.db.seed_data import COMMON_CURRENCIES" in migration_text
    assert "for currency in COMMON_CURRENCIES" in migration_text
    for code in ["RUB", "USD", "EUR", "GEL", "KZT", "TRY", "AED"]:
        assert code in seed_data_text
