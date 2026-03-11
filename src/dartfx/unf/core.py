# SPDX-FileCopyrightText: 2024-present kulnor <pascal@codata.org>
#
# SPDX-License-Identifier: MIT

"""Core UNF v6 computation – column, file, and dataset levels.

This module provides the three public entry-points of the library:

- ``unf_column``    – compute the UNF of a single Polars Series.
- ``unf_dataframe`` – compute the UNF of a Polars DataFrame.
- ``unf_file``      – compute the UNF of a CSV or Parquet file.
- ``unf_dataset``   – compute the combined UNF of multiple files.
- ``unf_from_bytes`` – compute the UNF from raw file bytes.
- ``unf_from_stream`` – compute the UNF from a file-like object.

For large files, ``unf_file`` automatically switches to streaming mode
when the file size exceeds a fraction of available system memory.  This
can also be controlled explicitly via the ``streaming`` parameter.
"""

from __future__ import annotations

import hashlib
import logging
from collections import OrderedDict
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, Literal, cast

import polars as pl

from dartfx.unf.hasher import combine_unfs, finalize_hash
from dartfx.unf.memory import should_stream
from dartfx.unf.normalize import (
    normalize_bit_field,
    normalize_boolean,
    normalize_date,
    normalize_datetime,
    normalize_duration,
    normalize_missing,
    normalize_numeric,
    normalize_string,
    normalize_time,
)
from dartfx.unf.parameters import UNFParameters
from dartfx.unf.report import ColumnResult, DatasetResult, FileResult, UNFReport
from dartfx.unf.schema import (
    json_schema_to_polars_schema,
    parse_schema_input,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Default batch size for streaming (number of rows per batch).
DEFAULT_BATCH_SIZE = 100_000


# ---------------------------------------------------------------------------
# Value-level normalization dispatch
# ---------------------------------------------------------------------------


def _normalize_value(
    value: object,
    dtype: pl.DataType,
    params: UNFParameters,
) -> bytes:
    """Normalize a single value based on its Polars dtype.

    Centralises the type-dispatch logic so it can be shared by both
    the in-memory and streaming code paths.
    """
    if value is None:
        return normalize_missing()

    if dtype in (pl.Boolean,):
        return normalize_boolean(value)  # type: ignore[arg-type]

    if dtype.is_numeric():
        return normalize_numeric(
            value,  # type: ignore[arg-type]
            digits=params.digits,
            truncate=params.truncate,
        )

    if dtype in (pl.Utf8, pl.Categorical, pl.Enum):
        return normalize_string(str(value), max_chars=params.characters)

    if dtype == pl.Date:
        assert isinstance(value, date)
        return normalize_date(value)

    if dtype == pl.Time:
        assert isinstance(value, time)
        return normalize_time(value)

    if dtype.is_(pl.Datetime) or isinstance(dtype, pl.Datetime):
        assert isinstance(value, datetime)
        return normalize_datetime(value)

    if dtype == pl.Duration:
        assert isinstance(value, timedelta)
        return normalize_duration(value)

    if dtype == pl.Binary:
        assert isinstance(value, bytes | bytearray)
        return normalize_bit_field(bytes(value))

    # Fallback: treat as string
    return normalize_string(str(value), max_chars=params.characters)


def _normalize_series(
    series: pl.Series,
    params: UNFParameters,
    null_handling: Literal["null-as-null", "null-as-string"] = "null-as-null",
) -> pl.Series:
    """Normalize a Polars Series into a Binary Series of UNF values.

    Leverages Polars vectorized expressions for simple types (Boolean, String, Date)
    to maximize performance. Complex types (Numeric, Time, Datetime, Duration)
    use `map_elements` to ensure strict spec compliance while still benefiting
    from Polars' batch processing.
    """
    dtype = series.dtype

    # 1. Handle Missing Values (UNF v6 §Ia.6)
    # Note: MISSING_VALUE (b"\x00\x00\x00") has no terminator.
    null_mask = series.is_null()

    expr: pl.Expr | pl.Series
    if dtype == pl.Boolean:
        # Vectorized Boolean (UNF v6 §Ia.3 -> §Ia.1)
        expr = (
            pl.when(series)
            .then(pl.lit(b"+1.e+\n\x00"))
            .otherwise(pl.lit(b"+0.e+\n\x00"))
        )
    elif dtype in (pl.Utf8, pl.Categorical, pl.Enum):
        # Vectorized String (UNF v6 §Ia.2)
        # Slicing and encoding to UTF-8 (Polars str is already UTF-8)
        expr = series.str.slice(0, params.characters).cast(pl.Binary) + pl.lit(
            b"\n\x00"
        )
    elif dtype == pl.Date:
        # Vectorized Date (UNF v6 §Ia.5a)
        # Format: YYYY-MM-DD
        expr = series.dt.to_string("%Y-%m-%d").cast(pl.Binary) + pl.lit(b"\n\x00")
    elif dtype.is_numeric():
        # Numeric still requires Decimal for precise ties-to-even rounding
        # We use map_elements for strict compliance.
        expr = series.map_elements(
            lambda x: normalize_numeric(
                x, digits=params.digits, truncate=params.truncate
            ),
            return_dtype=pl.Binary,
        )
    elif dtype == pl.Time:
        expr = series.map_elements(normalize_time, return_dtype=pl.Binary)
    elif dtype.is_(pl.Datetime) or isinstance(dtype, pl.Datetime):
        expr = series.map_elements(normalize_datetime, return_dtype=pl.Binary)
    elif dtype == pl.Duration:
        expr = series.map_elements(normalize_duration, return_dtype=pl.Binary)
    elif dtype == pl.Binary:
        expr = series.map_elements(normalize_bit_field, return_dtype=pl.Binary)
    else:
        # Fallback: treat as string
        expr = series.cast(pl.Utf8).str.slice(0, params.characters).cast(
            pl.Binary
        ) + pl.lit(b"\n\x00")

    # 2. Handle nulls based on null_handling mode
    if null_handling == "null-as-string" and dtype in (
        pl.Utf8,
        pl.Categorical,
        pl.Enum,
    ):
        # Dataverse-alignment: Treat nulls in string columns as empty strings ("\n\0")
        # because Dataverse's CSV reader (String.split) treats empty fields as "".
        null_replacement = b"\n\x00"
    else:
        # UNF spec default: missing values are 3 null bytes
        null_replacement = normalize_missing()

    # Apply the expression and handle nulls
    # We must handle nulls AFTER the expression to avoid map_elements
    # being called on nulls or expressions failing on nulls.
    final_series = pl.select(
        pl.when(null_mask).then(pl.lit(null_replacement)).otherwise(expr)
    ).to_series()

    return final_series


# ---------------------------------------------------------------------------
# Incremental hashing helpers
# ---------------------------------------------------------------------------


def _update_hasher_from_series(
    hasher: hashlib._Hash,  # noqa: SLF001
    series: pl.Series,
    params: UNFParameters,
    null_handling: Literal["null-as-null", "null-as-string"] = "null-as-null",
) -> None:
    """Feed normalised bytes from *series* into a SHA-256 *hasher*.

    Uses vectorized normalization where possible and joins chunks in C
    to minimize Python loop overhead.
    """
    normalized_series = _normalize_series(series, params, null_handling=null_handling)

    # We join all normalized bytes into a single blob before updating the hasher.
    # This replaces thousands of Python-level loop iterations and hasher calls
    # with a single optimized C-level join and one hasher update.
    # Note: to_list() on a Binary series returns a List[bytes].
    all_bytes = b"".join(normalized_series.to_list())
    hasher.update(all_bytes)


# ---------------------------------------------------------------------------
# Column (vector) level – spec §I
# ---------------------------------------------------------------------------


def unf_column(
    series: pl.Series,
    params: UNFParameters | None = None,
    null_handling: Literal["null-as-null", "null-as-string"] = "null-as-null",
) -> str:
    """Compute the UNF fingerprint of a single data vector (Polars Series).

    This function implements the UNF v6 specification for individual vectors, including
    type-specific normalization (numeric rounding, string truncation, bit-field
    encoding, etc.) and SHA-256 hashing.

    Parameters
    ----------
    series : pl.Series
        A Polars Series containing the data to fingerprint. Supports all standard Polars
        dtypes including Integers, Floats, Strings (Utf8), Booleans, Dates, Datetimes,
        and Durations.
    params : UNFParameters, optional
        Calculation parameters (digits, hash bits, etc.). If None, default UNF v6
        settings are used (N=7, H=128, X=128).
    null_handling: Literal["null-as-null", "null-as-string"], default "null-as-null"
        If "null-as-string", null values in string-like columns are normalized as
        empty strings (newline + null byte) instead of the UNF missing value
        representation (3 null bytes). This provides parity with the canonical
        Java Dataverse implementation's CSV parsing behavior.

    Returns
    -------
    str
        The printable UNF v6 fingerprint string
        (e.g., ``UNF:6:Do5dfAoOOFt4FSj0JcByEw==``).
    """
    if params is None:
        params = UNFParameters()

    hasher = hashlib.sha256()
    _update_hasher_from_series(hasher, series, params, null_handling=null_handling)
    return finalize_hash(hasher, params)


def _detect_column_type(dtype: pl.DataType) -> str:
    """Map a Polars dtype to a human-readable UNF type label."""
    if dtype == pl.Boolean:
        return "boolean"
    if dtype.is_numeric():
        return "numeric"
    if dtype in (pl.Utf8, pl.Categorical, pl.Enum):
        return "string"
    if dtype == pl.Date:
        return "date"
    if dtype.is_(pl.Datetime) or isinstance(dtype, pl.Datetime):
        return "datetime"
    if dtype == pl.Time:
        return "time"
    if dtype == pl.Duration:
        return "duration"
    if dtype == pl.Binary:
        return "binary"
    return "string"


# ---------------------------------------------------------------------------
# DataFrame (data frame) level – spec §IIa
# ---------------------------------------------------------------------------


def unf_dataframe(
    df: pl.DataFrame,
    *,
    params: UNFParameters | None = None,
    label: str | None = None,
    null_handling: Literal["null-as-null", "null-as-string"] = "null-as-null",
) -> UNFReport:
    """Compute the UNF fingerprint for a Polars DataFrame.

    Implements the "combination" rule for dataframes: individual column hashes are
    sorted lexicographically and then hashed together to form the table-level
    fingerprint. This ensures that the UNF is invariant to column order.

    Parameters
    ----------
    df : pl.DataFrame
        The Polars DataFrame to fingerprint.
    params : UNFParameters, optional
        Calculation parameters. Uses defaults if None.
    label : str, optional
        A human-readable label or filename for the report.
    null_handling: Literal["null-as-null", "null-as-string"], default "null-as-null"
        If "null-as-string", the implementation provides bit-for-bit parity with
        the canonical Java Dataverse CSV reader. Any column containing nulls is
        coerced to a string column, and those nulls are normalized as empty
        strings (`\\n\\x00`) instead of missing values (`\\x00\\x00\\x00`).

    Returns
    -------
    UNFReport
        A structured report containing the final UNF, individual column UNFs, and types.

    Examples
    --------
    >>> import polars as pl
    >>> from dartfx.unf import unf_dataframe
    >>> df = pl.DataFrame({"a": [1, 2], "b": [3.5, 4.5]})
    >>> report = unf_dataframe(df, label="my_table")
    >>> print(report.result.unf)
    UNF:6:L1XOn/hA9Y/p/v3N8XjH9A==
    >>> # Inspect columns in the report
    >>> for col in report.result.columns:
    ...     print(f"{col.name}: {col.unf}")
    """
    if params is None:
        params = UNFParameters()

    # Parallel column processing
    def process_column(col_name: str) -> tuple[str, str, str]:
        series = df.get_column(col_name)
        col_unf = unf_column(series, params, null_handling=null_handling)
        col_type = _detect_column_type(series.dtype)
        return col_name, col_unf, col_type

    column_results: list[ColumnResult] = []
    column_unfs: list[str] = []

    with ThreadPoolExecutor() as executor:
        # executor.map maintains submission order
        results = list(executor.map(process_column, df.columns))

    for col_name, col_unf, col_type in results:
        column_results.append(ColumnResult(name=col_name, unf=col_unf, type=col_type))
        column_unfs.append(col_unf)

    file_unf = combine_unfs(column_unfs, params)

    file_result = FileResult(
        unf=file_unf,
        columns=column_results,
        label=label or "dataframe",
    )

    report = UNFReport(result=file_result, params=params)
    report.options = {"null_handling": null_handling}
    return report


# ---------------------------------------------------------------------------
# File-format helpers
# ---------------------------------------------------------------------------


_CSV_EXTENSIONS = frozenset((".csv", ".tsv", ".txt", ".tab"))
_TAB_EXTENSIONS = frozenset((".tsv", ".tab"))
_STAT_EXTENSIONS = frozenset((".sav", ".zsav", ".dta", ".sas7bdat", ".xpt"))


def _get_separator(suffix: str) -> str:
    """Return the column separator for a CSV-family file extension."""
    return "\t" if suffix in _TAB_EXTENSIONS else ","


def _validate_suffix(suffix: str) -> None:
    """Raise ``ValueError`` if *suffix* is not a supported format."""
    if suffix not in (".parquet", *_CSV_EXTENSIONS, *_STAT_EXTENSIONS):
        msg = (
            f"Unsupported file format: {suffix!r}. Use .csv, .tsv, .tab, "
            ".txt, .parquet, .sav, .zsav, .dta, .sas7bdat, or .xpt."
        )
        raise ValueError(msg)


def _detect_csv_overrides(
    path: Path,
    separator: str,
    infer_schema_length: int,
    detect_leading_zeros: bool,
    detect_null_strings: bool,
) -> dict[str, str]:
    """Detect columns that should be forced to string in a CSV file.

    Checks the first `infer_schema_length` rows for:
    - Integer-like leading zeros (if `detect_leading_zeros=True`)
    - Null values in any column (if `detect_null_strings=True`)

    Returns a mapping of column names to "string" for overrides.
    """
    if infer_schema_length == 0:
        return {}

    if not detect_leading_zeros and not detect_null_strings:
        return {}

    # Read a sample of rows as strings to check for overrides.
    # We align this with the user-provided infer_schema_length.
    sample_size = None if infer_schema_length == -1 else infer_schema_length

    try:
        # We use pl.read_csv with infer_schema_length=0 to read as strings.
        # This is fast for a small sample and preserves leading zeros.
        df_sample = pl.read_csv(
            path,
            separator=separator,
            n_rows=sample_size,
            infer_schema_length=0,
        )
    except Exception:
        # If reading fails (e.g. empty file or weird format), skip detection.
        return {}

    overrides: dict[str, str] = {}
    for col in df_sample.columns:
        series = df_sample.get_column(col)
        is_string_override = False

        if detect_leading_zeros:
            # We look for a pattern: starts with '0', followed by digits, and has more
            # than 1 digit in total (e.g. "01" but not "0").
            # Regex: ^0[0-9]+$ matches strings consisting only of a leading zero
            # followed by one or more digits.
            if series.str.contains(r"^0[0-9]+$").any():
                is_string_override = True

        if not is_string_override and detect_null_strings:
            # Because infer_schema_length=0 treats empty fields as null strings
            if series.null_count() > 0:
                is_string_override = True

        if is_string_override:
            overrides[col] = "string"

    return overrides


# ---------------------------------------------------------------------------
# Batch iteration
# ---------------------------------------------------------------------------


def _iter_batches(
    path: Path,
    suffix: str,
    batch_size: int,
    infer_schema_length: int = 10_000,
    parse_dates: bool = True,
    schema_overrides: dict[str, pl.DataType] | None = None,
) -> Iterator[pl.DataFrame]:
    """Yield successive ``DataFrame`` batches from *path*.

    - **CSV**: uses ``pl.scan_csv().collect_batches()`` (Polars streaming).
    - **Parquet**: uses PyArrow's ``ParquetFile.iter_batches`` for true
      row-group-aware streaming, then converts each batch to Polars.
    """
    if suffix in _CSV_EXTENSIONS:
        yield from _iter_batches_csv(
            path,
            batch_size,
            _get_separator(suffix),
            infer_schema_length,
            parse_dates,
            schema_overrides,
        )
    elif suffix in _STAT_EXTENSIONS:
        yield from _iter_batches_stat(path, suffix, batch_size)
    else:
        yield from _iter_batches_parquet(path, batch_size, schema_overrides)


def _iter_batches_csv(
    path: Path,
    batch_size: int,
    separator: str,
    infer_schema_length: int = 10_000,
    parse_dates: bool = True,
    schema_overrides: dict[str, pl.DataType] | None = None,
) -> Iterator[pl.DataFrame]:
    """Yield CSV row batches via ``pl.scan_csv().collect_batches()``.

    Uses the modern Polars streaming API (``scan_csv`` + ``collect_batches``)
    which replaces the deprecated ``read_csv_batched``.
    """
    # -1 means scan all rows, so pass None to Polars
    schema_length = None if infer_schema_length == -1 else infer_schema_length
    lf = pl.scan_csv(
        path,
        separator=separator,
        infer_schema_length=schema_length,
        try_parse_dates=parse_dates,
        schema_overrides=schema_overrides,
    )
    yield from lf.collect_batches(chunk_size=batch_size)


def _iter_batches_parquet(
    path: Path,
    batch_size: int,
    schema_overrides: dict[str, pl.DataType] | None = None,
) -> Iterator[pl.DataFrame]:
    """Yield Parquet row batches via ``pyarrow.parquet``."""
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(path)
    for record_batch in pf.iter_batches(batch_size=batch_size):
        df = cast(pl.DataFrame, pl.from_arrow(record_batch))
        if schema_overrides:
            # Only cast columns that exist in the dataframe to avoid errors
            overrides = {
                k: v
                for k, v in schema_overrides.items()
                if k in df.columns and df[k].dtype != v
            }
            if overrides:
                df = df.cast(cast(Any, overrides))
        yield df


def _get_pyreadstat_func(suffix: str) -> Callable[..., Any]:
    """Return the appropriate pyreadstat reading function for a suffix."""
    import pyreadstat

    if suffix in (".sav", ".zsav"):
        return cast(Callable[..., Any], pyreadstat.read_sav)
    if suffix == ".dta":
        return cast(Callable[..., Any], pyreadstat.read_dta)
    if suffix == ".sas7bdat":
        return cast(Callable[..., Any], pyreadstat.read_sas7bdat)
    if suffix == ".xpt":
        return cast(Callable[..., Any], pyreadstat.read_xport)
    raise ValueError(f"Unsupported pyreadstat format: {suffix}")


def _iter_batches_stat(
    path: Path,
    suffix: str,
    batch_size: int,
) -> Iterator[pl.DataFrame]:
    """Yield statistical file row batches via pyreadstat."""
    import pyreadstat

    read_func = _get_pyreadstat_func(suffix)
    for pd_df, _meta in pyreadstat.read_file_in_chunks(
        read_func, path, chunksize=batch_size
    ):
        yield pl.from_pandas(pd_df)


def _parse_string_to_date_with_formats(
    col: pl.Expr,
    formats: list[str],
    col_name: str,
) -> pl.Expr:
    """Parse string column to date using explicit format strings.

    Handles mixed formats by trying each format and using coalesce
    to fill in values that failed with previous formats.

    Parameters
    ----------
    col : pl.Expr
        String column expression to parse.
    formats : list[str]
        List of Python strptime format strings to try.
    col_name : str
        Column name for logging.

    Returns
    -------
    pl.Expr
        Date expression.

    Raises
    ------
    ValueError
        If parsing fails with all provided formats.
    """
    if not formats:
        raise ValueError(f"No date formats provided for column '{col_name}'.")

    # Build a coalescing expression that tries each format
    # Start with the first format's parsed values
    result_expr = col.str.strptime(pl.Date, formats[0], strict=False)

    # Try subsequent formats for rows that failed with first format
    for fmt in formats[1:]:
        result_expr = pl.coalesce(
            result_expr,
            col.str.strptime(pl.Date, fmt, strict=False),
        )

    return result_expr


def _parse_string_to_datetime_with_formats(
    col: pl.Expr,
    formats: list[str],
    col_name: str,
) -> pl.Expr:
    """Parse string column to datetime using explicit format strings.

    Handles mixed formats by trying each format and using coalesce
    to fill in values that failed with previous formats.

    Parameters
    ----------
    col : pl.Expr
        String column expression to parse.
    formats : list[str]
        List of Python strptime format strings to try.
    col_name : str
        Column name for logging.

    Returns
    -------
    pl.Expr
        Datetime expression.

    Raises
    ------
    ValueError
        If parsing fails with all provided formats.
    """
    if not formats:
        raise ValueError(f"No datetime formats provided for column '{col_name}'.")

    # Build a coalescing expression that tries each format
    # Start with the first format's parsed values
    result_expr = col.str.strptime(pl.Datetime, formats[0], strict=False)

    # Try subsequent formats for rows that failed with first format
    for fmt in formats[1:]:
        result_expr = pl.coalesce(
            result_expr,
            col.str.strptime(pl.Datetime, fmt, strict=False),
        )

    return result_expr


# ---------------------------------------------------------------------------
# File (data frame) level – spec §IIa
# ---------------------------------------------------------------------------


def _apply_schema_to_dataframe(
    df: pl.DataFrame,
    user_schema: dict[str, str] | dict[str, dict[str, Any]],
) -> pl.DataFrame:
    """Apply user-provided schema overrides to a DataFrame.

    Converts column types according to the user-provided schema.
    Handles both simple type specifications and full schema objects
    with format specifications for date/datetime columns.
    Attempts to cast all columns to the specified types.
    Raises an error if any cast fails.

    Parameters
    ----------
    df : pl.DataFrame
        The DataFrame to apply overrides to.
    user_schema : dict[str, str] or dict[str, dict]
        Mapping of column names to JSON Schema type names (dict[str, str])
        or full schema objects (dict[str, dict[str, Any]]).

    Returns
    -------
    pl.DataFrame
        The DataFrame with overridden types.

    Raises
    ------
    ValueError
        If any column cannot be cast to the user-specified type.
    """
    from dartfx.unf.schema import (
        _extract_primary_type,
        extract_date_formats_from_schema,
    )

    # Extract type mapping and schema objects
    column_types: dict[str, str] = {}
    column_schemas: dict[str, dict[str, Any]] = {}

    for col_name, col_spec in user_schema.items():
        if isinstance(col_spec, dict):
            # Full schema object with potential format/oneOf properties
            column_schemas[col_name] = col_spec
            if "type" in col_spec:
                primary_type = _extract_primary_type(col_spec["type"])
                if primary_type:
                    column_types[col_name] = primary_type
        elif isinstance(col_spec, str):
            # Simple type string
            column_types[col_name] = col_spec

    # Convert user schema to Polars types
    polars_schema = json_schema_to_polars_schema(column_types)

    # Get current schema
    current_schema = dict(df.schema)

    # Apply overrides
    for col_name, target_type in polars_schema.items():
        if col_name not in current_schema:
            logger.warning(
                "Schema specifies column '%s' which doesn't exist in data", col_name
            )
            continue

        current_type = current_schema[col_name]
        if current_type != target_type:
            # Attempt to cast to the user-specified type
            logger.warning(
                "Casting column '%s' from %s to %s",
                col_name,
                current_type,
                target_type,
            )
            try:
                col = pl.col(col_name)
                # If source is string and target is not string, replace empty
                # strings with null to allow proper casting
                if current_type == pl.Utf8 and target_type != pl.Utf8:
                    col = pl.when(col == "").then(None).otherwise(col)

                # Get column schema if available for format info
                col_schema = column_schemas.get(col_name)

                # Special handling for date/datetime with format specifications
                if target_type == pl.Date and current_type == pl.Utf8:
                    if col_schema:
                        formats = extract_date_formats_from_schema(col_schema)
                        if formats:
                            col = _parse_string_to_date_with_formats(
                                col, formats, col_name
                            )
                        else:
                            # No format specified, try standard ISO
                            col = col.str.strptime(pl.Date, "%Y-%m-%d")
                    else:
                        # No schema, try standard ISO
                        col = col.str.strptime(pl.Date, "%Y-%m-%d")
                elif target_type == pl.Datetime and current_type == pl.Utf8:
                    if col_schema:
                        formats = extract_date_formats_from_schema(col_schema)
                        if formats:
                            col = _parse_string_to_datetime_with_formats(
                                col, formats, col_name
                            )
                        else:
                            # No format specified, try standard ISO
                            col = col.str.strptime(pl.Datetime, "%Y-%m-%dT%H:%M:%S")
                    else:
                        # No schema, try standard ISO
                        col = col.str.strptime(pl.Datetime, "%Y-%m-%dT%H:%M:%S")
                else:
                    # Standard cast for other types
                    col = col.cast(target_type)

                # Always alias to ensure the column name is preserved
                df = df.with_columns(col.alias(col_name))
            except Exception as e:
                raise ValueError(
                    f"Failed to cast column '{col_name}' from {current_type} to "
                    f"{target_type}: {e}"
                ) from e

    return df


# ---------------------------------------------------------------------------
# File (data frame) level – spec §IIa
# ---------------------------------------------------------------------------


def unf_file(
    path: str | Path,
    *,
    params: UNFParameters | None = None,
    label: str | None = None,
    streaming: bool | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    infer_schema_length: int = 10_000,
    schema: str | Path | dict[str, Any] | None = None,
    parse_dates: bool = True,
    detect_leading_zeros: bool = False,
    null_handling: Literal["null-as-null", "null-as-string"] = "null-as-null",
) -> UNFReport:
    """Compute the UNF fingerprint for a CSV or Parquet data file.

    This is the main entry point for file-based fingerprinting. It handles schema
    inference, format detection, and performance optimization based on file size.

    Parameters
    ----------
    path : str or Path
        Path to a CSV or Parquet data file.
    params : UNFParameters, optional
        Normalization parameters (digits, characters, hash_bits, truncate).
    label : str, optional
        Human-readable label for the file in the report.
    streaming : bool, optional
        If ``True``, force streaming mode (process in batches, constant memory).
        If ``False``, force in-memory mode. If ``None`` (the default),
        auto-detect based on file size vs. available system memory.
    batch_size : int
        Number of rows per batch in streaming mode (default 100 000).
    infer_schema_length : int
        Number of rows to scan for CSV schema inference (default 10 000).
        Use -1 to scan all rows.
    schema : str, Path, dict, or None
        Optional schema specification to override type inference.
        Can be:
        - Path to a JSON Schema file
        - Inline JSON Schema string
        - Dictionary mapping column names to JSON Schema type names
        User-specified types take precedence over inferred types.
    parse_dates : bool, default True
        If True, attempt to auto-parse date and datetime columns in CSV files.
    detect_leading_zeros : bool, default False
        If True, auto-detect columns with leading zeros (e.g. '01') and treat
        them as strings to preserve the zeros. Disabled by default.
    null_handling: Literal["null-as-null", "null-as-string"], default "null-as-null"
        If "null-as-string", the implementation provides bit-for-bit parity with
        the canonical Java Dataverse CSV reader. Any column containing nulls is
        coerced to a string column, and those nulls are normalized as empty
        strings (`\\n\\x00`) instead of missing values (`\\x00\\x00\\x00`).

    Returns
    -------
    UNFReport
        A structured report containing column-level and file-level UNFs.

    Raises
    ------
    ValueError
        If the file format is not supported or schema is invalid.

    Examples
    --------
    >>> # With schema file
    >>> report = unf_file("data.csv", schema="schema.json")
    >>>
    >>> # With inline schema
    >>> schema_json = '{"properties": {"age": {"type": "integer"}}}'
    >>> report = unf_file("data.csv", schema=schema_json)
    >>>
    >>> # With dictionary
    >>> report = unf_file("data.csv", schema={"age": "integer", "name": "string"})
    """
    if params is None:
        params = UNFParameters()

    path = Path(path)
    suffix = path.suffix.lower()
    _validate_suffix(suffix)

    # Parse and validate schema input with full schema objects (for format support)
    parsed_schema = (
        parse_schema_input(schema, return_full_schema=True) if schema else {}
    )

    # Force full file scan for CSV schemas if null-as-string is requested
    if null_handling == "null-as-string" and suffix in _CSV_EXTENSIONS:
        infer_schema_length = -1

    # Auto-detect overrides for CSV files (leading zeros, null-as-string)
    if suffix in _CSV_EXTENSIONS:
        csv_overrides = _detect_csv_overrides(
            path,
            _get_separator(suffix),
            infer_schema_length,
            detect_leading_zeros,
            null_handling == "null-as-string",
        )
        if csv_overrides:
            # Merge: user-provided schema wins
            for col in csv_overrides:
                if parsed_schema is None or col not in parsed_schema:
                    if parsed_schema is None:
                        parsed_schema = {}
                    parsed_schema[col] = {"type": "string"}

    if not parsed_schema:
        parsed_schema = None

    polars_overrides: dict[str, pl.DataType] = {}
    if parsed_schema:
        for col_name, col_spec in parsed_schema.items():
            if isinstance(col_spec, dict) and col_spec.get("type") == "string":
                polars_overrides[col_name] = pl.String()

    # --- decide processing mode ---
    if streaming is None:
        streaming = should_stream(path)

    if streaming and null_handling == "null-as-string":
        logger.warning(
            "Streaming is strictly disabled for %s files when using "
            "'--null-as-string' in order to guarantee correct null inferences. "
            "Forcing in-memory mode.",
            suffix,
        )
        streaming = False

    if streaming:
        logger.info(
            "Processing %s in streaming mode (batch_size=%d)", path.name, batch_size
        )
        report = _unf_file_streaming(
            path,
            suffix,
            params,
            label,
            batch_size,
            infer_schema_length,
            parsed_schema,
            parse_dates,
            polars_overrides,
            null_handling,
        )
    else:
        logger.info("Processing %s in-memory", path.name)
        report = _unf_file_memory(
            path,
            suffix,
            params,
            label,
            infer_schema_length,
            parsed_schema,
            parse_dates,
            polars_overrides,
            null_handling,
        )

    report.options = {
        "streaming": streaming,
        "batch_size": batch_size,
        "infer_schema_length": infer_schema_length,
        "parse_dates": parse_dates,
        "detect_leading_zeros": detect_leading_zeros,
        "null_handling": null_handling,
    }
    return report


def _unf_file_memory(
    path: Path,
    suffix: str,
    params: UNFParameters,
    label: str | None,
    infer_schema_length: int = 10_000,
    user_schema: dict[str, str] | dict[str, dict[str, Any]] | None = None,
    parse_dates: bool = True,
    polars_overrides: dict[str, pl.DataType] | None = None,
    null_handling: Literal["null-as-null", "null-as-string"] = "null-as-null",
) -> UNFReport:
    """Process a file entirely in memory with parallel column hashing."""
    if polars_overrides is None:
        polars_overrides = {}

    if suffix == ".parquet":
        df = pl.read_parquet(path)
    elif suffix in _STAT_EXTENSIONS:
        read_func = _get_pyreadstat_func(suffix)
        pd_df, _meta = read_func(path)
        df = pl.from_pandas(pd_df)
    else:  # CSV and other text-based formats
        # -1 means scan all rows, so pass None to Polars
        schema_length = None if infer_schema_length == -1 else infer_schema_length
        df = pl.read_csv(
            path,
            separator=_get_separator(suffix),
            infer_schema_length=schema_length,
            try_parse_dates=parse_dates,
            schema_overrides=polars_overrides,
        )

    # Apply schema overrides if provided
    if user_schema:
        df = _apply_schema_to_dataframe(df, user_schema)

    if null_handling == "null-as-string":
        null_counts = df.select(pl.all().null_count()).row(0)
        null_cols = [
            col
            for col, count in zip(df.columns, null_counts, strict=True)
            if count > 0 and df[col].dtype != pl.String
        ]
        if null_cols:
            df = df.cast(dict.fromkeys(null_cols, pl.String))

    report = unf_dataframe(
        df, params=params, label=label or path.name, null_handling=null_handling
    )
    return report


def _unf_file_streaming(
    path: Path,
    suffix: str,
    params: UNFParameters,
    label: str | None,
    batch_size: int,
    infer_schema_length: int = 10_000,
    user_schema: dict[str, str] | dict[str, dict[str, Any]] | None = None,
    parse_dates: bool = True,
    polars_overrides: dict[str, pl.DataType] | None = None,
    null_handling: Literal["null-as-null", "null-as-string"] = "null-as-null",
) -> UNFReport:
    """Process a file in streaming mode using incremental SHA-256 hashers.

    Maintains one ``hashlib.sha256()`` per column.  Each batch of rows
    is normalised and fed into the corresponding hasher via ``.update()``.
    After all batches, each hasher is finalised into a column UNF.  This
    keeps memory usage proportional to ``batch_size`` regardless of total
    file size.
    """
    # Ordered dict preserves original column order.
    column_hashers: OrderedDict[str, hashlib._Hash] = OrderedDict()  # noqa: SLF001
    column_types: dict[str, str] = {}
    rows_processed = 0

    if polars_overrides is None:
        polars_overrides = {}

    with ThreadPoolExecutor() as executor:
        for _batch_idx, batch_df in enumerate(
            _iter_batches(
                path,
                suffix,
                batch_size,
                infer_schema_length,
                parse_dates,
                polars_overrides,
            )
        ):
            batch_rows = len(batch_df)

            # First batch: initialise per-column hashers and apply schema overrides.
            if not column_hashers:
                # Apply schema overrides if provided
                if user_schema:
                    batch_df = _apply_schema_to_dataframe(batch_df, user_schema)

                for col_name in batch_df.columns:
                    column_hashers[col_name] = hashlib.sha256()
                    column_types[col_name] = _detect_column_type(
                        batch_df.get_column(col_name).dtype,
                    )

            # Feed this batch's data into each column's hasher in parallel.
            def update_col(col_name: str, df: pl.DataFrame = batch_df) -> None:
                series = df.get_column(col_name)
                _update_hasher_from_series(
                    column_hashers[col_name], series, params, null_handling
                )

            # executor.map or submit. Here we just want to run them all.
            list(executor.map(update_col, column_hashers.keys()))

            rows_processed += batch_rows
            logger.debug(
                "Streamed %d rows from %s (total: %d)",
                batch_rows,
                path.name,
                rows_processed,
            )

    if not column_hashers:
        msg = f"No data found in {path}"
        raise ValueError(msg)

    logger.info(
        "Finished streaming %s: %d rows across %d columns",
        path.name,
        rows_processed,
        len(column_hashers),
    )

    # Finalise per-column hashes.
    column_results: list[ColumnResult] = []
    column_unfs: list[str] = []

    for col_name, hasher in column_hashers.items():
        col_unf = finalize_hash(hasher, params)
        column_results.append(
            ColumnResult(name=col_name, unf=col_unf, type=column_types[col_name]),
        )
        column_unfs.append(col_unf)

    file_unf = combine_unfs(column_unfs, params)
    file_result = FileResult(
        unf=file_unf,
        columns=column_results,
        label=label or path.name,
    )
    return UNFReport(result=file_result, params=params)


# ---------------------------------------------------------------------------
# Dataset level – spec §IIb
# ---------------------------------------------------------------------------


def unf_dataset(
    paths: Sequence[str | Path],
    *,
    params: UNFParameters | None = None,
    label: str | None = None,
    streaming: bool | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    infer_schema_length: int = 10_000,
    schema: str | Path | dict[str, Any] | None = None,
    parse_dates: bool = True,
    detect_leading_zeros: bool = False,
    null_handling: Literal["null-as-null", "null-as-string"] = "null-as-null",
) -> UNFReport:
    """Compute the combined UNF of multiple files (e.g. a partitioned dataset).

    Equivalent to the UNF of a collection of files as per UNF v6 §IIb.
    Individual file fingerprints are computed, sorted lexicographically, and hashed.

    Parameters
    ----------
    paths : list of Path or str
        List of files to process.
    params : UNFParameters, optional
        Common parameters for all files.
    label : str, optional
        Label for the entire dataset.
    streaming : bool, optional
        Whether to use streaming mode for individual files.
    batch_size : int, optional
        Rows per batch for streaming.
    infer_schema_length : int, optional
        Number of rows to scan for CSV schema inference. Use -1 to scan all rows.
    schema : str, Path, dict, or None
        Optional schema specification to override type inference for all files.
        Same format as in ``unf_file()``.
    parse_dates : bool, default True
        If True, attempt to auto-parse date and datetime columns in CSV files.
    detect_leading_zeros : bool, default False
        If True, auto-detect columns with leading zeros (e.g. '01') and treat
        them as strings to preserve the zeros. Disabled by default.
    null_handling: Literal["null-as-null", "null-as-string"], default "null-as-null"
        If "null-as-string", the implementation provides bit-for-bit parity with
        the canonical Java Dataverse CSV reader. Any column containing nulls is
        coerced to a string column, and those nulls are normalized as empty
        strings (`\\n\\x00`) instead of missing values (`\\x00\\x00\\x00`).

    Returns
    -------
    UNFReport
        A report containing the dataset-level UNF and a collection of file-level
        results.

    Examples
    --------
    >>> from dartfx.unf import unf_dataset
    >>> files = ["part-1.parquet", "part-2.parquet"]
    >>> ds_report = unf_dataset(files, label="Version_1")
    >>> print(f"Unified UNF: {ds_report.result.unf}")
    """
    if params is None:
        params = UNFParameters()

    # Parallel file processing
    def process_file(p: str | Path) -> FileResult:
        report = unf_file(
            p,
            params=params,
            streaming=streaming,
            batch_size=batch_size,
            infer_schema_length=infer_schema_length,
            schema=schema,
            parse_dates=parse_dates,
            detect_leading_zeros=detect_leading_zeros,
            null_handling=null_handling,
        )
        assert isinstance(report.result, FileResult)
        return report.result

    with ThreadPoolExecutor() as executor:
        results = list(executor.map(process_file, paths))

    file_results: list[FileResult] = []
    file_unfs: list[str] = []

    for res in results:
        file_results.append(res)
        file_unfs.append(res.unf)

    dataset_unf = combine_unfs(file_unfs, params)

    dataset_result = DatasetResult(
        unf=dataset_unf,
        entries=file_results,
        label=label or "",
    )

    report = UNFReport(result=dataset_result, params=params)
    report.options = {
        "streaming": streaming,
        "batch_size": batch_size,
        "infer_schema_length": infer_schema_length,
        "parse_dates": parse_dates,
        "detect_leading_zeros": detect_leading_zeros,
        "null_handling": null_handling,
    }
    return report


def unf_from_bytes(
    data: bytes,
    format: str,  # noqa: A002
    *,
    params: UNFParameters | None = None,
    label: str | None = None,
    parse_dates: bool = True,
) -> UNFReport:
    """Compute the UNF from raw file bytes.

    Parameters
    ----------
    data : bytes
        The raw bytes of a CSV or Parquet file.
    format : str
        Either "csv" or "parquet".
    params : UNFParameters, optional
        Calculation parameters.
    label : str, optional
        A human-readable label for the report.
    parse_dates : bool, default True
        If True, attempt to auto-parse date and datetime columns in CSV datasets.

    Returns
    -------
    UNFReport
        A structured UNF report.
    """
    return unf_from_stream(
        BytesIO(data), format, params=params, label=label, parse_dates=parse_dates
    )


def unf_from_stream(
    stream: BinaryIO,
    format: str,  # noqa: A002
    *,
    params: UNFParameters | None = None,
    label: str | None = None,
    parse_dates: bool = True,
) -> UNFReport:
    """Compute the UNF from a file-like object.

    Parameters
    ----------
    stream : BinaryIO
        A file-like object (e.g. from ``open(..., 'rb')`` or ``BytesIO``).
    format : str
        Either "csv" or "parquet".
    params : UNFParameters, optional
        Calculation parameters.
    label : str, optional
        A human-readable label for the report.
    parse_dates : bool, default True
        If True, attempt to auto-parse date and datetime columns in CSV streams.

    Returns
    -------
    UNFReport
        A structured UNF report.
    """
    if format.lower() == "parquet":
        df = pl.read_parquet(stream)
    elif format.lower() == "csv":
        df = pl.read_csv(
            stream, infer_schema_length=10_000, try_parse_dates=parse_dates
        )
    else:
        msg = f"Unsupported format: {format!r}. Use 'csv' or 'parquet'."
        raise ValueError(msg)

    report = unf_dataframe(df, params=params, label=label or "stream")
    report.options = {
        "format": format,
        "parse_dates": parse_dates,
    }
    return report
