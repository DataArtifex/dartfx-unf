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
from typing import TYPE_CHECKING, Any, Literal, overload

import polars as pl

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Map JSON Schema types to Polars data types
JSON_TO_POLARS_TYPE_MAP: dict[str, type[pl.DataType]] = {
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

# Map JSON Schema format strings to Python strptime patterns
# Handles common format specifications for dates and datetimes
FORMAT_TO_STRPTIME: dict[str, str] = {
    # ISO 8601 formats
    "date": "%Y-%m-%d",  # Standard ISO date
    "time": "%H:%M:%S",  # Standard time
    "date-time": "%Y-%m-%dT%H:%M:%S",  # ISO datetime
    # Common variants
    "yyyy-mm-dd": "%Y-%m-%d",
    "yy-mm-dd": "%y-%m-%d",
    "dd-mm-yyyy": "%d-%m-%Y",
    "dd-mm-yy": "%d-%m-%y",
    "mm-dd-yyyy": "%m-%d-%Y",
    "mm-dd-yy": "%m-%d-%y",
    "dd.mm.yyyy": "%d.%m.%Y",
    "dd.mm.yy": "%d.%m.%y",
    "mm.dd.yyyy": "%m.%d.%Y",
    "mm.dd.yy": "%m.%d.%y",
    "dd/mm/yyyy": "%d/%m/%Y",
    "dd/mm/yy": "%d/%m/%y",
    "mm/dd/yyyy": "%m/%d/%Y",
    "mm/dd/yy": "%m/%d/%y",
    # With time
    "yyyy-mm-dd hh:mm:ss": "%Y-%m-%d %H:%M:%S",
    "dd-mm-yyyy hh:mm:ss": "%d-%m-%Y %H:%M:%S",
    "dd.mm.yyyy hh:mm:ss": "%d.%m.%Y %H:%M:%S",
    # Timezone-aware (remove TZ info, will handle separately if needed)
    "yyyy-mm-ddThh:mm:ss": "%Y-%m-%dT%H:%M:%S",
    "dd-mm-yyyyThh:mm:ss": "%d-%m-%YT%H:%M:%S",
}


def _extract_primary_type(type_spec: str | list[str]) -> str | None:
    """Extract a single non-null type from a JSON Schema type field.

    Handles union types e.g. ["string", "null"] -> "string".
    """
    if isinstance(type_spec, str):
        return type_spec if type_spec != "null" else None

    if isinstance(type_spec, list):
        # Prefer the first non-null type
        for t in type_spec:
            if t != "null":
                return t
    return None


def _resolve_primary_type(schema_property: dict[str, Any]) -> str | None:
    """Extract the primary data type from a JSON Schema type specification.

    Handles both simple types (string) and union types (list).
    Filters out "null" type and returns the primary data type.

    Parameters
    ----------
    schema_property : dict[str, Any]
        A dictionary representing a column's schema property, e.g.,
        {"type": "integer"} or {"type": ["integer", "null"]}.

    Returns
    -------
    str or None
        The primary (non-null) type, or None if only "null" is specified.

    Examples
    --------
    >>> _resolve_primary_type({"type": "integer"})
    'integer'
    >>> _resolve_primary_type({"type": ["integer", "null"]})
    'integer'
    >>> _resolve_primary_type({"type": ["null", "string"]})
    'string'
    >>> _resolve_primary_type({"type": ["null"]})
    None
    """
    type_spec = schema_property.get("type")
    if type_spec is None:
        return None

    if isinstance(type_spec, str):
        return _extract_primary_type(type_spec)
    elif isinstance(type_spec, list):
        return _extract_primary_type(type_spec)
    return None


def extract_date_formats_from_schema(
    schema_property: dict[str, Any],
) -> list[str] | None:
    """Extract date/time format strings from a JSON Schema column definition.

    Supports both single format and multiple formats via oneOf:
    - Single format: {"format": "dd-mm-yyyy"}
    - Multiple formats: {"oneOf": [{"format": "dd-mm-yyyy"}, {"format": "mm-dd-yyyy"}]}

    Maps JSON format strings to Python strptime patterns.

    Parameters
    ----------
    schema_property : dict[str, Any]
        Full column schema object from JSON Schema.

    Returns
    -------
    list[str] or None
        List of Python strptime format strings (e.g., ['%d-%m-%Y', '%m-%d-%Y']),
        or None if no format is specified or recognized.

    Examples
    --------
    >>> schema = {"type": "date", "format": "dd-mm-yyyy"}
    >>> extract_date_formats_from_schema(schema)
    ['%d-%m-%Y']

    >>> schema = {"type": "date", "oneOf": [
    ...     {"format": "dd-mm-yyyy"},
    ...     {"format": "mm-dd-yyyy"}
    ... ]}
    >>> extract_date_formats_from_schema(schema)
    ['%d-%m-%Y', '%m-%d-%Y']
    """
    formats: list[str] = []

    # Check for single format property
    if "format" in schema_property:
        fmt = schema_property["format"]
        if isinstance(fmt, str):
            # Case-insensitive lookup and convert to lowercase for matching
            fmt_lower = fmt.lower()
            if fmt_lower in FORMAT_TO_STRPTIME:
                formats.append(FORMAT_TO_STRPTIME[fmt_lower])
            else:
                logger.warning(
                    "Unknown date format '%s' in schema; will use auto-detection", fmt
                )

    # Check for oneOf property (multiple format alternatives)
    if "oneOf" in schema_property:
        one_of = schema_property["oneOf"]
        if isinstance(one_of, list):
            for alternative in one_of:
                if isinstance(alternative, dict) and "format" in alternative:
                    fmt = alternative["format"]
                    if isinstance(fmt, str):
                        fmt_lower = fmt.lower()
                        if fmt_lower in FORMAT_TO_STRPTIME:
                            strptime_fmt = FORMAT_TO_STRPTIME[fmt_lower]
                            if strptime_fmt not in formats:  # Avoid duplicates
                                formats.append(strptime_fmt)
                        else:
                            logger.warning(
                                "Unknown date format '%s' in oneOf; skipping", fmt
                            )

    return formats if formats else None


@overload
def parse_schema_file(
    path: str | Path, return_full_schema: Literal[False] = False
) -> dict[str, str]: ...


@overload
def parse_schema_file(
    path: str | Path, return_full_schema: Literal[True]
) -> dict[str, dict[str, Any]]: ...


@overload
def parse_schema_file(
    path: str | Path, return_full_schema: bool = False
) -> dict[str, str] | dict[str, dict[str, Any]]: ...


def parse_schema_file(
    path: str | Path, return_full_schema: bool = False
) -> dict[str, str] | dict[str, dict[str, Any]]:
    """Parse a JSON Schema file and extract column definitions.

    Expects a JSON object with a "properties" key containing column definitions.
    Each property should have a "type" field and optional "format", "oneOf", etc.

    Parameters
    ----------
    path : str or Path
        Path to the JSON Schema file.
    return_full_schema : bool, optional
        If True (default), return full schema objects. If False, return type names.

    Returns
    -------
    dict[str, str] or dict[str, dict[str, Any]]
        If return_full_schema=True: Full schema objects with format info.
        If return_full_schema=False: Just type name strings.

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
            schema_dict: dict[str, Any] = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in schema file: {e}") from e

    if not isinstance(schema_dict, dict):
        raise ValueError("Schema must be a JSON object")

    # Extract properties from JSON Schema format
    properties: dict[str, Any] = schema_dict.get("properties", {})
    if not properties:
        logger.warning("No 'properties' found in schema")
        return {} if return_full_schema else {}

    if return_full_schema:
        result: dict[str, dict[str, Any]] = {}
        for col_name, col_schema in properties.items():
            if isinstance(col_schema, dict):
                result[col_name] = col_schema
            elif isinstance(col_schema, str):
                result[col_name] = {"type": col_schema}
        return result

    column_types: dict[str, str] = {}
    for col_name, col_schema in properties.items():
        if isinstance(col_schema, dict):
            primary_type = _resolve_primary_type(col_schema)
            if primary_type:
                column_types[col_name] = primary_type
            else:
                logger.warning(
                    "No primary type found for column '%s' (only null specified)",
                    col_name,
                )
        elif isinstance(col_schema, str):
            column_types[col_name] = col_schema

    return column_types


@overload
def parse_schema_inline(
    schema_json: str, return_full_schema: Literal[False] = False
) -> dict[str, str]: ...


@overload
def parse_schema_inline(
    schema_json: str, return_full_schema: Literal[True]
) -> dict[str, dict[str, Any]]: ...


@overload
def parse_schema_inline(
    schema_json: str, return_full_schema: bool = False
) -> dict[str, str] | dict[str, dict[str, Any]]: ...


def parse_schema_inline(
    schema_json: str, return_full_schema: bool = False
) -> dict[str, str] | dict[str, dict[str, Any]]:
    """Parse an inline JSON Schema string.

    Parameters
    ----------
    schema_json : str
        JSON string with column type definitions
    return_full_schema : bool, optional
        If True (default), return full schema objects. If False, return type names.

    Returns
    -------
    dict[str, str] or dict[str, dict[str, Any]]
        If return_full_schema=True: Full schema objects with format info.
        If return_full_schema=False: Just type name strings.

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
        schema_dict: dict[str, Any] = json.loads(schema_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON schema: {e}") from e

    if not isinstance(schema_dict, dict):
        raise ValueError("Schema must be a JSON object")

    # Support both direct format and properties format
    properties: dict[str, Any] = schema_dict.get("properties", schema_dict)

    if return_full_schema:
        result: dict[str, dict[str, Any]] = {}
        for col_name, col_schema in properties.items():
            if isinstance(col_schema, dict):
                result[col_name] = col_schema
            elif isinstance(col_schema, str):
                result[col_name] = {"type": col_schema}
        return result

    column_types: dict[str, str] = {}
    for col_name, col_schema in properties.items():
        if isinstance(col_schema, dict):
            primary_type = _resolve_primary_type(col_schema)
            if primary_type:
                column_types[col_name] = primary_type
            else:
                logger.warning(
                    "No primary type found for column '%s' (only null specified)",
                    col_name,
                )
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
        polars_schema[col_name] = JSON_TO_POLARS_TYPE_MAP[json_type]()

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
        If True, allow overriding any type. If False, raise an error on
        type mismatches (except for new columns).

    Returns
    -------
    dict[str, pl.DataType]
        The merged schema with user overrides applied.

    Raises
    ------
    ValueError
        If a column type doesn't match user-specified type and
        allow_loose_cast is False.
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
            if allow_loose_cast:
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


@overload
def parse_schema_input(
    schema_input: str | Path | dict[str, Any] | None,
    return_full_schema: Literal[False] = False,
) -> dict[str, str] | None: ...


@overload
def parse_schema_input(
    schema_input: str | Path | dict[str, Any] | None,
    return_full_schema: Literal[True],
) -> dict[str, dict[str, Any]] | None: ...


@overload
def parse_schema_input(
    schema_input: str | Path | dict[str, Any] | None,
    return_full_schema: bool = False,
) -> dict[str, str] | dict[str, dict[str, Any]] | None: ...


def parse_schema_input(
    schema_input: str | Path | dict[str, Any] | None,
    return_full_schema: bool = False,
) -> dict[str, str] | dict[str, dict[str, Any]] | None:
    """Parse various schema input formats into a schema dictionary.

    Handles:
    - File path to JSON Schema
    - Inline JSON Schema string
    - Already-parsed dictionary (with or without "properties" wrapper)

    Parameters
    ----------
    schema_input : str, Path, dict, or None
        Schema input in various formats.
    return_full_schema : bool, optional
        If True (default), return full column schema objects (preserves
        format, oneOf, etc.). If False, return only type names for
        backward compatibility.

    Returns
    -------
    dict[str, str], dict[str, dict], or None
        If return_full_schema=True: Mapping of column names to full schema dicts.
        If return_full_schema=False: Mapping of column names to type names.
        Returns None if no input.

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
        # Handle dicts with or without "properties" wrapper
        if "properties" in schema_input:
            # Full JSON Schema format with "properties" key
            properties = schema_input["properties"]
        else:
            # Direct mapping of column definitions
            properties = schema_input

        if return_full_schema:
            # Return full schema objects
            result: dict[str, dict[str, Any]] = {}
            for col_name, col_spec in properties.items():
                if isinstance(col_spec, dict):
                    result[col_name] = col_spec
                elif isinstance(col_spec, str):
                    # Convert simple type strings to schema objects
                    result[col_name] = {"type": col_spec}
            return result

        # Return just type names
        result_types: dict[str, str] = {}
        for col_name, col_spec in properties.items():
            if isinstance(col_spec, dict) and "type" in col_spec:
                primary_type = _extract_primary_type(col_spec["type"])
                if primary_type:
                    result_types[col_name] = primary_type
            elif isinstance(col_spec, str):
                result_types[col_name] = col_spec
        return result_types

    if isinstance(schema_input, (str, Path)):
        schema_str = str(schema_input)
        path = Path(schema_str)

        if path.exists():
            if return_full_schema:
                return parse_schema_file(path, return_full_schema=True)
            return parse_schema_file(path, return_full_schema=False)

        # Try parsing as inline JSON
        if schema_str.startswith("{"):
            if return_full_schema:
                return parse_schema_inline(schema_str, return_full_schema=True)
            return parse_schema_inline(schema_str, return_full_schema=False)

        # Neither file nor valid JSON
        raise ValueError(
            f"Schema input '{schema_str}' is neither a valid file path "
            f"nor valid JSON. Provide a path to a JSON Schema file "
            f"or a JSON string."
        )

    raise TypeError(
        f"schema_input must be str, Path, dict, or None; got {type(schema_input)}"
    )
