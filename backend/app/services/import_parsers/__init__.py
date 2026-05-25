from app.services.csv_imports import CsvColumnMapping, ParsedCsvRow, parse_csv_rows
from app.services.import_parsers.freedom import (
    FREEDOM_PARSER_VERSION,
    parse_freedom_rows,
)

GENERIC_CSV_PARSER_VERSION = "csv-v1"
SUPPORTED_IMPORT_PARSERS = frozenset({"generic_csv", "freedom"})


def parser_version(parser_name: str) -> str:
    if parser_name == "freedom":
        return FREEDOM_PARSER_VERSION
    if parser_name == "generic_csv":
        return GENERIC_CSV_PARSER_VERSION
    raise ValueError(f"Unsupported import parser: {parser_name}")


def parse_import_rows(
    content: str,
    *,
    parser_name: str = "generic_csv",
    column_mapping: CsvColumnMapping | None,
) -> list[ParsedCsvRow]:
    if parser_name == "freedom":
        return parse_freedom_rows(content)
    if parser_name == "generic_csv":
        if column_mapping is None:
            raise ValueError("generic_csv imports require column_mapping")
        return parse_csv_rows(content, column_mapping)
    raise ValueError(f"Unsupported import parser: {parser_name}")
