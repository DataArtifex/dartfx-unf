# SPDX-FileCopyrightText: 2024-present kulnor <pascal@codata.org>
#
# SPDX-License-Identifier: MIT

"""Schema handling for type specification and override of automatic inference.

This module provides utilities to:

- Parse user-provided JSON Schema definitions
- Map JSON Schema types to Polars data types
- Apply schema overrides to inferred schemas
- Handle type conflicts with customizable error handling
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Map JSON Schema types to Polars data types
JSON_TO_POLARS_TYPE_MAP: dict[str, pl.DataType] = {
    "null": pl.Null,
    "boolean": pl.Boolean,
    "integer": pl.Int64,
    "number": pl.Float64,
    "string": pl.Utf8,
    "array": pl.List,
    "object": pl.Struct,
    "date": pl.Date,
    "date-time": pl.Datetime,
    "time": pl.Time,
    "duration": pl.Duration,
}

# Format strings for date/time types (common formats)
ISO_8601_FORMATS = {
    "date": "%Y-%m-%d",
    "time": "%H:%M:%S",
    "date-time": "%Y-%m-%dT%H:%M:%S",
}


def parse_schema_file(path: str | Path) -> dict[str, str]:
    """Parse a JSON Schema file and extract column type definitions.

    Expects a JSON object with a "properties" key containing column definitions.
    Each property should have a "type" field.

    Parameters
    ----------
    path : str or Path
        Path to the JSON Schema file.

    Returns
    -------
    dict[str, str]
        Mapping of column names to JSON Schema type names.

    Raises
    ------
    FileNotFoundError
        If the schema file does not exist.
    ValueError
        If the schema is invalid.

    Examples
    --------
    >>> schema = parse_schema_file("schema.json")
    >>> schema
    {'age': 'integer', 'name': 'string', 'date_joined': 'date'}
    """
    schema_path = Path(path)
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    try:
        with open(schema_path) as f:
            schema_dict = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in schema file: {e}") from e

    if not isinstance(schema_dict, dict):
        raise ValueError("Schema must be a JSON object")

    # Extract properties from JSON Schema format
    properties = schema_dict.get("properties", {})
    if not properties:
        logger.warning("No 'properties' found in schema")
        return {}

    column_types: dict[str, str] = {}
    for col_name, col_schema in properties.items():
        if isinstance(col_schema, dict) and "type" in col_schema:
            column_types[col_name] = col_schema["type"]

    return column_types


def parse_schema_inline(schema_json: str) -> dict[str, str]:
    """Parse an inline JSON Schema string.

    Parameters
    ----------
    schema_json : str
        JSON string with column type definitions.

    Returns
    -------
    dict[str, str]
        Mapping of column names to JSON Schema type names.

    Raises
    ------
    ValueError
        If the JSON is invalid.

    Examples
    --------
    >>> schema_json = '{"age": {"type": "integer"}}'
    >>> schema = parse_schema_inline(schema_json)
    >>> schema
    {'age': 'integer'}
    """
    try:
        schema_dict = json.loads(schema_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON schema: {e}") from e

    if not isinstance(schema_dict, dict):
        raise ValueError("Schema must be a JSON object")

    # Support both direct format and properties format
    properties = schema_dict.get("properties", schema_dict)

    column_types: dict[str, str] = {}
    for col_name, col_schema in properties.items():
        if isinstance(col_schema, dict) and "type" in col_schema:
            column_types[col_name] = col_schema["type"]
        elif isinstance(col_schema, str):
            # Allow shorthand: {"age": "integer"}
            column_types[col_name] = col_schema

    return column_types


def json_schema_to_polars_schema(
    column_types: dict[str, str],
) -> dict[str, pl.DataType]:
    """Convert JSON Schema type names to Polars data types.

    Parameters
    ----------
    column_types : dict[str, str]
        Mapping of column names to JSON Schema type names.

    Returns
    -------
    dict[str, pl.DataType]
        Mapping of column names to Polars data types.

    Raises
    ------
    ValueError
        If a type is not recognized.
    """
    polars_schema: dict[str, pl.DataType] = {}

    for col_name, json_type in column_types.items():
        if json_type not in JSON_TO_POLARS_TYPE_MAP:
            raise ValueError(
                f"Unsupported type '{json_type}' for column '{col_name}'. "
                f"Supported types: {', '.join(JSON_TO_POLARS_TYPE_MAP.keys())}"
            )
        polars_schema[col_name] = JSON_TO_POLARS_TYPE_MAP[json_type]

    return polars_schema


def apply_schema_override(
    inferred_schema: dict[str, pl.DataType],
    user_schema: dict[str, pl.DataType] | None,
    allow_loose_cast: bool = True,
) -> dict[str, pl.DataType]:
    """Apply user-provided schema overrides to an inferred schema.

    User-specified types take precedence over inferred types. Partial schemas
    are supported (only specified columns are overridden).

    Parameters
    ----------
    inferred_schema : dict[str, pl.DataType]
        The schema inferred by Polars.
    user_schema : dict[str, pl.DataType] or None
        User-provided type overrides. None means no overrides.
    allow_loose_cast : bool
        If True, allow casting string columns to any type with a warning.
        If False, raise an error on type mismatches.

    Returns
    -------
    dict[str, pl.DataType]
        The merged schema with user overrides applied.

    Raises
    ------
    ValueError
        If a non-string column type doesn't match user-specified type.
    """
    if user_schema is None:
        return inferred_schema

    merged_schema = inferred_schema.copy()

    for col_name, user_type in user_schema.items():
        inferred_type = inferred_schema.get(col_name)

        if inferred_type is None:
            # Column doesn't exist in inferred schema; add it
            merged_schema[col_name] = user_type
            logger.info(
                "Schema override: new column '%s' with type %s", col_name, user_type
            )
        elif inferred_type != user_type:
            if inferred_type == pl.Utf8 or allow_loose_cast:
                logger.warning(
                    "Schema override: column '%s' inferred as %s, overriding to %s",
                    col_name,
                    inferred_type,
                    user_type,
                )
                merged_schema[col_name] = user_type
            else:
                raise ValueError(
                    f"Type mismatch for column '{col_name}': "
                    f"inferred {inferred_type}, user specified {user_type}. "
                    f"Set allow_loose_cast=True to force override."
                )

    return merged_schema


def parse_schema_input(
    schema_input: str | Path | dict[str, str] | None,
) -> dict[str, str] | None:
    """Parse various schema input formats into a column type dictionary.

    Handles:
    - File path to JSON Schema
    - Inline JSON Schema string
    - Already-parsed dictionary

    Parameters
    ----------
    schema_input : str, Path, dict, or None
        Schema input in various formats.

    Returns
    -------
    dict[str, str] or None
        Mapping of column names to JSON Schema type names, or None if no input.

    Raises
    ------
    ValueError
        If the input format is invalid.
    FileNotFoundError
        If a file path is provided but doesn't exist.
    """
    if schema_input is None:
        return None

    if isinstance(schema_input, dict):
        return schema_input

    if isinstance(schema_input, (str, Path)):
        schema_str = str(schema_input)
        path = Path(schema_str)

        if path.exists():
            return parse_schema_file(path)

        # Try parsing as inline JSON
        if schema_str.startswith("{"):
            return parse_schema_inline(schema_str)

        # Neither file nor valid JSON
        raise ValueError(
            f"Schema input '{schema_str}' is neither a valid file path "
            f"nor valid JSON. Provide a path to a JSON Schema file "
            f"or a JSON string."
        )

    raise TypeError(
        f"schema_input must be str, Path, dict, or None; got {type(schema_input)}"
    )
