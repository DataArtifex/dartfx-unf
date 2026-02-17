# SPDX-FileCopyrightText: 2024-present kulnor <pascal@codata.org>
#
# SPDX-License-Identifier: MIT

"""Tests for schema specification and type override functionality."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import polars as pl

from dartfx.unf import (
    parse_schema_file,
    parse_schema_inline,
    parse_schema_input,
    unf_file,
)
from dartfx.unf.schema import (
    json_schema_to_polars_schema,
)


class TestSchemaParser:
    """Test schema parsing functions."""

    def test_parse_schema_file(self):
        """Test parsing a JSON Schema file."""
        schema = {
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
                "salary": {"type": "number"},
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(schema, f)
            f.flush()
            temp_path = f.name

        try:
            result = parse_schema_file(temp_path)
            assert result == {"id": "integer", "name": "string", "salary": "number"}
        finally:
            Path(temp_path).unlink()

    def test_parse_schema_inline(self):
        """Test parsing inline JSON schema."""
        schema_json = (
            '{"properties": {"id": {"type": "integer"}, "name": {"type": "string"}}}'
        )
        result = parse_schema_inline(schema_json)
        assert result == {"id": "integer", "name": "string"}

    def test_parse_schema_input_file(self):
        """Test parse_schema_input with file path."""
        schema = {"properties": {"x": {"type": "number"}}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(schema, f)
            f.flush()
            temp_path = f.name

        try:
            result = parse_schema_input(temp_path)
            assert result == {"x": "number"}
        finally:
            Path(temp_path).unlink()

    def test_parse_schema_input_inline(self):
        """Test parse_schema_input with inline JSON."""
        schema_json = '{"properties": {"x": {"type": "integer"}}}'
        result = parse_schema_input(schema_json)
        assert result == {"x": "integer"}

    def test_parse_schema_input_dict(self):
        """Test parse_schema_input with dictionary."""
        schema_dict = {"id": "integer", "name": "string"}
        result = parse_schema_input(schema_dict)
        assert result == schema_dict

    def test_parse_schema_input_none(self):
        """Test parse_schema_input with None."""
        result = parse_schema_input(None)
        assert result is None


class TestJsonSchemaToPolarsSchema:
    """Test JSON Schema to Polars type mapping."""

    def test_basic_type_mapping(self):
        """Test mapping basic JSON Schema types."""
        column_types = {
            "age": "integer",
            "name": "string",
            "height": "number",
            "active": "boolean",
        }
        result = json_schema_to_polars_schema(column_types)

        assert result["age"] == pl.Int64
        assert result["name"] == pl.Utf8
        assert result["height"] == pl.Float64
        assert result["active"] == pl.Boolean

    def test_date_time_types(self):
        """Test date/time type mappings."""
        column_types = {
            "start_date": "date",
            "birth_time": "time",
            "created_at": "date-time",
        }
        result = json_schema_to_polars_schema(column_types)

        assert result["start_date"] == pl.Date
        assert result["birth_time"] == pl.Time
        assert result["created_at"] == pl.Datetime


class TestSchemaWithFiles:
    """Test schema override with actual files."""

    def test_unf_file_with_schema_dict(self, tmp_path):
        """Test unf_file with schema as dictionary."""
        # Create a test CSV
        csv_content = "id,name,value\n1,Alice,100.5\n2,Bob,200.75"
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        schema = {"id": "integer", "name": "string", "value": "number"}

        # Should not raise an error
        report = unf_file(csv_file, schema=schema)
        assert report.result.unf is not None

    def test_unf_file_with_schema_file(self, tmp_path):
        """Test unf_file with schema from file."""
        # Create test CSV
        csv_content = "id,name\n1,Alice\n2,Bob"
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        # Create schema file
        schema = {"properties": {"id": {"type": "integer"}, "name": {"type": "string"}}}
        schema_file = tmp_path / "schema.json"
        schema_file.write_text(json.dumps(schema))

        # Should not raise an error
        report = unf_file(csv_file, schema=str(schema_file))
        assert report.result.unf is not None

    def test_unf_file_with_inline_schema(self, tmp_path):
        """Test unf_file with inline JSON schema."""
        # Create test CSV
        csv_content = "x,y\n1.5,2.5\n3.5,4.5"
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        schema_json = (
            '{"properties": {"x": {"type": "number"}, "y": {"type": "number"}}}'
        )

        # Should not raise an error
        report = unf_file(csv_file, schema=schema_json)
        assert report.result.unf is not None

    def test_schema_consistency(self, tmp_path):
        """Test that same schema produces same UNF regardless of input format."""
        # Create test CSV
        csv_content = "col_a,col_b\nval1,10\nval2,20"
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)

        schema_dict = {"col_a": "string", "col_b": "integer"}

        # Create schema file
        schema_obj = {
            "properties": {"col_a": {"type": "string"}, "col_b": {"type": "integer"}}
        }
        schema_file = tmp_path / "schema.json"
        schema_file.write_text(json.dumps(schema_obj))

        # Calculate UNF with three schema formats
        report1 = unf_file(csv_file, schema=schema_dict)
        report2 = unf_file(csv_file, schema=str(schema_file))
        schema_str = (
            '{"properties": {"col_a": {"type": "string"}, '
            '"col_b": {"type": "integer"}}}'
        )
        report3 = unf_file(csv_file, schema=schema_str)

        # All should produce the same UNF
        assert report1.result.unf == report2.result.unf
        assert report2.result.unf == report3.result.unf
