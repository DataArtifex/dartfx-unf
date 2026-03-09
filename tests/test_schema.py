"""Tests for JSON Schema format-based date/datetime parsing."""

from pathlib import Path
from typing import Any

from dartfx.unf.core import unf_file
from dartfx.unf.report import FileResult


class TestSchemaFormatBasedParsing:
    """Test date/datetime parsing using JSON Schema format property."""

    def test_date_format_from_schema_format_property(self, tmp_path: Path) -> None:
        """Test date parsing using JSON Schema format property."""
        csv_file = tmp_path / "dates.csv"
        csv_file.write_text("date_col,value\n15.03.2024,100\n20.05.2024,200\n")

        # Schema with explicit format property for DD.MM.YYYY
        schema: dict[str, Any] = {
            "properties": {
                "date_col": {"type": "date", "format": "dd.mm.yyyy"},
                "value": {"type": "integer"},
            }
        }

        report = unf_file(csv_file, schema=schema)
        assert isinstance(report.result, FileResult)
        assert report.result.unf is not None

        col_types = {col.name: col.type for col in report.result.columns}
        assert col_types["date_col"] == "date"
        assert col_types["value"] == "numeric"

    def test_date_multiple_formats_via_oneof(self, tmp_path: Path) -> None:
        """Test date parsing with multiple formats via oneOf."""
        csv_file = tmp_path / "mixed_dates.csv"
        csv_file.write_text("date_col,value\n15.03.2024,100\n20-05-2024,200\n")

        # Schema with multiple format alternatives via oneOf
        schema: dict[str, Any] = {
            "properties": {
                "date_col": {
                    "type": "date",
                    "oneOf": [{"format": "dd.mm.yyyy"}, {"format": "dd-mm-yyyy"}],
                },
                "value": {"type": "integer"},
            }
        }

        report = unf_file(csv_file, schema=schema)
        assert isinstance(report.result, FileResult)
        assert report.result.unf is not None

        col_types = {col.name: col.type for col in report.result.columns}
        assert col_types["date_col"] == "date"

    def test_datetime_format_from_schema(self, tmp_path: Path) -> None:
        """Test datetime parsing with explicit format."""
        csv_file = tmp_path / "datetimes.csv"
        csv_file.write_text(
            "timestamp,event\n15.03.2024 14:30:00,start\n20.05.2024 16:45:30,stop\n"
        )

        # Schema with datetime format
        schema: dict[str, Any] = {
            "properties": {
                "timestamp": {"type": "date-time", "format": "dd.mm.yyyy hh:mm:ss"},
                "event": {"type": "string"},
            }
        }

        report = unf_file(csv_file, schema=schema)
        assert isinstance(report.result, FileResult)
        assert report.result.unf is not None

        col_types = {col.name: col.type for col in report.result.columns}
        assert col_types["timestamp"] == "datetime"
