# SPDX-FileCopyrightText: 2024-present kulnor <pascal@codata.org>
#
# SPDX-License-Identifier: MIT

from pathlib import Path

import polars as pl

from dartfx.unf.core import unf_column, unf_dataframe, unf_dataset
from dartfx.unf.normalize import normalize_bit_field
from dartfx.unf.parameters import UNFParameters
from dartfx.unf.report import DatasetResult


class TestBitFields:
    """Tests for UNF v6 §Ia.4 Bit fields."""

    def test_normalize_bit_field_basic(self) -> None:
        # b'\x01' -> normalized to 'AQ==\n\x00'
        # Base64 of b'\x01' is 'AQ=='
        assert normalize_bit_field(b"\x01") == b"AQ==\n\x00"

    def test_normalize_bit_field_leading_zeros(self) -> None:
        # b'\x00\x01' -> 00000000 00000001 -> truncates to 1
        # aligned to byte: 00000001 -> b'\x01'
        assert normalize_bit_field(b"\x00\x01") == b"AQ==\n\x00"

    def test_normalize_bit_field_large(self) -> None:
        # 258 -> b'\x01\x02' (00000001 00000010)
        # Base64 of b'\x01\x02' is 'AQI='
        assert normalize_bit_field(b"\x01\x02") == b"AQI=\n\x00"
        assert normalize_bit_field(b"\x00\x01\x02") == b"AQI=\n\x00"

    def test_normalize_bit_field_zero(self) -> None:
        # All zeros should result in empty byte string Base64 encoded ("")
        assert normalize_bit_field(b"\x00\x00") == b"\n\x00"
        assert normalize_bit_field(b"") == b"\n\x00"

    def test_binary_column_unf(self) -> None:
        s = pl.Series("bin", [b"\x01", b"\x00\x01", b"\x01\x02"], dtype=pl.Binary)
        # These are b'\x01', b'\x01', b'\x01\x02' after normalization
        # They should produce a consistent UNF
        unf = unf_column(s)
        assert unf.startswith("UNF:6:")


class TestEdgeCases:
    """Tests for Phase 1 edge cases (large integers, mixed types, empty datasets)."""

    def test_large_integers(self) -> None:
        # Polars Int64 can handle up to 2^63 - 1
        large_val = 2**60
        s = pl.Series("large", [large_val], dtype=pl.Int64)
        unf1 = unf_column(s)

        # Should be same as float if precision allows
        s2 = pl.Series("large_f", [float(large_val)], dtype=pl.Float64)
        unf2 = unf_column(s2)
        assert unf1 == unf2

    def test_mixed_type_sensitivity(self) -> None:
        # UNF should be type-agnostic for values that normalize to the same string
        # e.g. 1 (int), 1.0 (float), True (bool) all normalize to +1.e+
        s1 = pl.Series("int", [1], dtype=pl.Int64)
        s2 = pl.Series("float", [1.0], dtype=pl.Float64)
        s3 = pl.Series("bool", [True], dtype=pl.Boolean)

        assert unf_column(s1) == unf_column(s2)
        assert unf_column(s2) == unf_column(s3)

    def test_empty_dataframe(self) -> None:
        # Empty DF (zero rows)
        df = pl.DataFrame({"a": [], "b": []}, schema={"a": pl.Int64, "b": pl.Utf8})
        report = unf_dataframe(df)
        assert report.result.unf.startswith("UNF:6:")

    def test_dataframe_no_columns(self) -> None:
        # Dataframe with rows but no columns (Polars allows this sometimes,
        # but usually we compute combined UNF of columns)
        # If no columns, combine_unfs([]) should handle it.
        from dartfx.unf.hasher import combine_unfs

        assert combine_unfs([], UNFParameters()) is not None

    def test_empty_dataset(self) -> None:
        # Dataset with no files is valid and produces an empty-set UNF
        report = unf_dataset([])
        assert report.result.unf.startswith("UNF:6:")
        assert isinstance(report.result, DatasetResult)

    def test_single_row_file(self, tmp_path: Path) -> None:
        p = tmp_path / "single.csv"
        p.write_text("a,b\n1,foo")
        report = unf_dataset([p])
        assert report.result.unf.startswith("UNF:6:")
