"""Tests for streaming and out-of-core processing.

Verifies that streaming mode produces identical UNFs to in-memory
processing, and tests the memory detection utilities.
"""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path

import polars as pl
import pytest

from dartfx.unf.core import unf_file
from dartfx.unf.memory import get_available_memory, should_stream
from dartfx.unf.parameters import UNFParameters

# ---------------------------------------------------------------------------
# Memory detection
# ---------------------------------------------------------------------------


class TestMemoryDetection:
    """Verify system memory utilities."""

    def test_get_available_memory_returns_positive(self):
        mem = get_available_memory()
        assert mem > 0

    def test_get_available_memory_reasonable_range(self):
        """Detected memory should be between 128 MB and 16 TB."""
        mem = get_available_memory()
        assert mem >= 128 * 1024 * 1024  # at least 128 MB
        assert mem <= 16 * 1024**4  # at most 16 TB

    def test_should_stream_small_file(self, tmp_path):
        """A tiny file should not trigger streaming."""
        small_file = tmp_path / "small.csv"
        small_file.write_text("a,b\n1,2\n3,4\n")
        assert should_stream(small_file) is False

    def test_should_stream_respects_fraction(self, tmp_path):
        """With a very low fraction, even a small file triggers streaming."""
        small_file = tmp_path / "small.csv"
        small_file.write_text("a,b\n1,2\n3,4\n")
        # fraction=0.0 means threshold is 0 bytes, so any file streams
        assert should_stream(small_file, memory_fraction=0.0) is True


# ---------------------------------------------------------------------------
# Fixtures: create temporary CSV and Parquet files
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_csv(tmp_path: Path) -> Path:
    """Create a small CSV with mixed types for testing."""
    df = pl.DataFrame(
        {
            "int_col": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "float_col": [1.1, 2.2, 3.3, None, 5.5, 6.6, 7.7, 8.8, 9.9, 0.0],
            "str_col": ["a", "bb", "ccc", "dddd", "e", "ff", "ggg", "hh", "i", "jj"],
            "bool_col": [
                True,
                False,
                True,
                False,
                True,
                False,
                True,
                False,
                True,
                False,
            ],
        }
    )
    path = tmp_path / "sample.csv"
    df.write_csv(path)
    return path


@pytest.fixture()
def sample_parquet(tmp_path: Path) -> Path:
    """Create a small Parquet file with mixed types for testing."""
    df = pl.DataFrame(
        {
            "id": list(range(50)),
            "value": [float(i) * 1.23456789 for i in range(50)],
            "label": [f"item_{i:03d}" for i in range(50)],
        }
    )
    path = tmp_path / "sample.parquet"
    df.write_parquet(path)
    return path


@pytest.fixture()
def date_csv(tmp_path: Path) -> Path:
    """Create a CSV with date-like columns for testing datetime streaming."""
    df = pl.DataFrame(
        {
            "date_col": [date(2020, 1, i + 1) for i in range(10)],
            "time_col": [time(i, 30, 0) for i in range(10)],
            "datetime_col": [datetime(2020, 1, i + 1, 12, 0, 0) for i in range(10)],
        }
    )
    # Write to Parquet to preserve types (CSV would lose date types).
    path = tmp_path / "dates.parquet"
    df.write_parquet(path)
    return path


# ---------------------------------------------------------------------------
# Core streaming tests: streaming == in-memory
# ---------------------------------------------------------------------------


class TestStreamingEquivalence:
    """Verify that streaming and in-memory modes produce identical UNFs."""

    def test_csv_streaming_matches_memory(self, sample_csv: Path):
        report_mem = unf_file(sample_csv, streaming=False)
        report_stream = unf_file(sample_csv, streaming=True, batch_size=3)

        assert report_mem.result.unf == report_stream.result.unf

    def test_csv_column_unfs_match(self, sample_csv: Path):
        report_mem = unf_file(sample_csv, streaming=False)
        report_stream = unf_file(sample_csv, streaming=True, batch_size=3)

        mem_col_unfs = {c.name: c.unf for c in report_mem.result.columns}
        stream_col_unfs = {c.name: c.unf for c in report_stream.result.columns}

        assert mem_col_unfs == stream_col_unfs

    def test_parquet_streaming_matches_memory(self, sample_parquet: Path):
        report_mem = unf_file(sample_parquet, streaming=False)
        report_stream = unf_file(sample_parquet, streaming=True, batch_size=10)

        assert report_mem.result.unf == report_stream.result.unf

    def test_parquet_column_unfs_match(self, sample_parquet: Path):
        report_mem = unf_file(sample_parquet, streaming=False)
        report_stream = unf_file(sample_parquet, streaming=True, batch_size=10)

        mem_col_unfs = {c.name: c.unf for c in report_mem.result.columns}
        stream_col_unfs = {c.name: c.unf for c in report_stream.result.columns}

        assert mem_col_unfs == stream_col_unfs

    def test_dates_streaming_matches_memory(self, date_csv: Path):
        report_mem = unf_file(date_csv, streaming=False)
        report_stream = unf_file(date_csv, streaming=True, batch_size=3)

        assert report_mem.result.unf == report_stream.result.unf

    def test_streaming_single_row_batches(self, sample_csv: Path):
        """Extreme: 1 row per batch should still produce correct UNF."""
        report_mem = unf_file(sample_csv, streaming=False)
        report_stream = unf_file(sample_csv, streaming=True, batch_size=1)

        assert report_mem.result.unf == report_stream.result.unf

    def test_streaming_larger_than_file_batch(self, sample_csv: Path):
        """Batch size larger than file should behave like in-memory."""
        report_mem = unf_file(sample_csv, streaming=False)
        report_stream = unf_file(sample_csv, streaming=True, batch_size=1_000_000)

        assert report_mem.result.unf == report_stream.result.unf


# ---------------------------------------------------------------------------
# Non-default parameters with streaming
# ---------------------------------------------------------------------------


class TestStreamingWithParameters:
    def test_non_default_digits(self, sample_csv: Path):
        params = UNFParameters(digits=9)
        report_mem = unf_file(sample_csv, params=params, streaming=False)
        report_stream = unf_file(
            sample_csv, params=params, streaming=True, batch_size=3
        )

        assert report_mem.result.unf == report_stream.result.unf

    def test_truncation_mode(self, sample_csv: Path):
        params = UNFParameters(truncate=True)
        report_mem = unf_file(sample_csv, params=params, streaming=False)
        report_stream = unf_file(
            sample_csv, params=params, streaming=True, batch_size=4
        )

        assert report_mem.result.unf == report_stream.result.unf

    def test_larger_hash_bits(self, sample_parquet: Path):
        params = UNFParameters(hash_bits=256)
        report_mem = unf_file(sample_parquet, params=params, streaming=False)
        report_stream = unf_file(
            sample_parquet, params=params, streaming=True, batch_size=5
        )

        assert report_mem.result.unf == report_stream.result.unf


# ---------------------------------------------------------------------------
# Larger file test
# ---------------------------------------------------------------------------


class TestStreamingLargerData:
    """Test streaming with a moderately-sized dataset."""

    def test_1000_row_csv(self, tmp_path: Path):
        n = 1_000
        df = pl.DataFrame(
            {
                "id": list(range(n)),
                "x": [float(i) * 0.001 for i in range(n)],
                "label": [f"row_{i}" for i in range(n)],
            }
        )
        path = tmp_path / "large.csv"
        df.write_csv(path)

        report_mem = unf_file(path, streaming=False)
        report_stream = unf_file(path, streaming=True, batch_size=100)

        assert report_mem.result.unf == report_stream.result.unf

    def test_1000_row_parquet(self, tmp_path: Path):
        n = 1_000
        df = pl.DataFrame(
            {
                "a": list(range(n)),
                "b": [float(i) ** 0.5 for i in range(n)],
                "c": [None if i % 7 == 0 else f"val_{i}" for i in range(n)],
            }
        )
        path = tmp_path / "large.parquet"
        df.write_parquet(path)

        report_mem = unf_file(path, streaming=False)
        report_stream = unf_file(path, streaming=True, batch_size=150)

        assert report_mem.result.unf == report_stream.result.unf


# ---------------------------------------------------------------------------
# Auto-detection
# ---------------------------------------------------------------------------


class TestAutoDetection:
    """Test the auto-detection logic in unf_file."""

    def test_auto_small_file_uses_memory(self, sample_csv: Path):
        """A small test file should auto-select in-memory mode."""
        # Just verify it completes successfully — auto mode should pick in-memory.
        report = unf_file(sample_csv)  # streaming=None (auto)
        assert report.result.unf.startswith("UNF:6:")

    def test_explicit_streaming_overrides_auto(self, sample_csv: Path):
        """Explicit streaming=True should work even for small files."""
        report = unf_file(sample_csv, streaming=True, batch_size=2)
        assert report.result.unf.startswith("UNF:6:")
