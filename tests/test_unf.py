"""Tests for UNF v6 normalization against official test vectors.

Test vectors sourced from:
https://raw.githubusercontent.com/IQSS/UNF/master/doc/unf_examples.txt
"""

from datetime import UTC, date, datetime, time, timedelta, timezone

import polars as pl
import pytest

from dartfx.unf.core import unf_column
from dartfx.unf.hasher import compute_unf_hash
from dartfx.unf.normalize import (
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

# ---------------------------------------------------------------
# §Ia.1 – Numeric normalization
# ---------------------------------------------------------------


class TestNormalizeNumeric:
    """Verify numeric normalization against the official examples."""

    def test_zero(self) -> None:
        assert normalize_numeric(0) == b"+0.e+\n\x00"

    def test_positive_zero_float(self) -> None:
        assert normalize_numeric(0.0) == b"+0.e+\n\x00"

    def test_negative_zero(self) -> None:
        assert normalize_numeric(-0.0) == b"-0.e+\n\x00"

    def test_one(self) -> None:
        assert normalize_numeric(1) == b"+1.e+\n\x00"

    def test_negative_300(self) -> None:
        assert normalize_numeric(-300) == b"-3.e+2\n\x00"

    def test_pi_5_digits(self) -> None:
        # pi at 5 significant digits -> +3.1415e+
        assert normalize_numeric(3.1415, digits=5) == b"+3.1415e+\n\x00"

    def test_small_number(self) -> None:
        assert normalize_numeric(0.00073) == b"+7.3e-4\n\x00"

    def test_rounding_ties_to_even_down(self) -> None:
        """1.2345675 rounds to 1.234568 (ties to even, round UP)."""
        result = normalize_numeric(1.2345675)
        assert result == b"+1.234568e+\n\x00"

    def test_rounding_ties_to_even_same(self) -> None:
        """1.2345685 also rounds to 1.234568 (ties to even, round DOWN)."""
        result = normalize_numeric(1.2345685)
        assert result == b"+1.234568e+\n\x00"

    def test_default_rounding(self) -> None:
        """1.23456789 at default 7 digits -> +1.234568e+"""
        result = normalize_numeric(1.23456789)
        assert result == b"+1.234568e+\n\x00"

    def test_nan(self) -> None:
        assert normalize_numeric(float("nan")) == b"+nan\n\x00"

    def test_positive_inf(self) -> None:
        assert normalize_numeric(float("inf")) == b"+inf\n\x00"

    def test_negative_inf(self) -> None:
        assert normalize_numeric(float("-inf")) == b"-inf\n\x00"


# ---------------------------------------------------------------
# §Ia.2 – String normalization
# ---------------------------------------------------------------


class TestNormalizeString:
    def test_simple_string(self) -> None:
        result = normalize_string("A character String")
        assert result == b"A character String\n\x00"

    def test_empty_string(self) -> None:
        result = normalize_string("")
        assert result == b"\n\x00"

    def test_long_string_truncation(self) -> None:
        long_str = (
            "A quite long character string, so long that the number of "
            "characters in it happens to be more than the default cutoff "
            "limit of 128."
        )
        result = normalize_string(long_str, max_chars=128)
        # Should be truncated at 128 chars + \n\0
        decoded = result.decode("utf-8")
        assert decoded.endswith("\n\x00")
        content = decoded[:-2]  # strip terminator
        assert len(content) == 128

    def test_utf8_accented(self) -> None:
        """Test 'på Færøerne' encodes correctly in UTF-8."""
        result = normalize_string("på Færøerne")
        # Must contain the correct UTF-8 byte sequences
        assert b"p\xc3\xa5 F\xc3\xa6r\xc3\xb8erne\n\x00" == result


# ---------------------------------------------------------------
# §Ia.3 – Boolean normalization
# ---------------------------------------------------------------


class TestNormalizeBoolean:
    def test_true(self) -> None:
        assert normalize_boolean(True) == b"+1.e+\n\x00"

    def test_false(self) -> None:
        assert normalize_boolean(False) == b"+0.e+\n\x00"


# ---------------------------------------------------------------
# §Ia.6 – Missing values
# ---------------------------------------------------------------


class TestMissing:
    def test_missing(self) -> None:
        assert normalize_missing() == b"\x00\x00\x00"


# ---------------------------------------------------------------
# Full UNF hashing – single-value vectors from official examples
# ---------------------------------------------------------------


class TestUNFHash:
    """Test complete UNF computation against official test vectors."""

    params = UNFParameters()

    def _unf_of_single(self, normalized_bytes: bytes) -> str:
        return compute_unf_hash(normalized_bytes, self.params)

    def test_zero(self) -> None:
        unf = self._unf_of_single(b"+0.e+\n\x00")
        assert unf == "UNF:6:YUvj33xEHnzirIHQyZaHow=="

    def test_one(self) -> None:
        unf = self._unf_of_single(b"+1.e+\n\x00")
        assert unf == "UNF:6:tv3XYCv524AfmlFyVOhuZg=="

    def test_negative_300(self) -> None:
        unf = self._unf_of_single(b"-3.e+2\n\x00")
        assert unf == "UNF:6:ZTXyg54FoMfRDWZl6oWmFQ=="

    def test_pi(self) -> None:
        unf = self._unf_of_single(b"+3.1415e+\n\x00")
        assert unf == "UNF:6:vOSZmXXXpKfQcqZ0Cuu5/w=="

    def test_small_number(self) -> None:
        unf = self._unf_of_single(b"+7.3e-4\n\x00")
        assert unf == "UNF:6:qhw3qzg3fEK0NNfoVxk4jQ=="

    def test_nan(self) -> None:
        unf = self._unf_of_single(b"+nan\n\x00")
        assert unf == "UNF:6:GNcR8/UCnImaPpw47gdPNg=="

    def test_positive_inf(self) -> None:
        unf = self._unf_of_single(b"+inf\n\x00")
        assert unf == "UNF:6:MdAI70WZdDHnu6qmkpqUQg=="

    def test_negative_inf(self) -> None:
        unf = self._unf_of_single(b"-inf\n\x00")
        assert unf == "UNF:6:A7orv3pgAhljFnGjQVLCog=="

    def test_character_string(self) -> None:
        unf = self._unf_of_single(b"A character String\n\x00")
        assert unf == "UNF:6:FYqU7uBl885eHMbpco1ooA=="

    def test_empty_string(self) -> None:
        unf = self._unf_of_single(b"\n\x00")
        assert unf == "UNF:6:ECtRuXZaVqPomffPDuOOUg=="

    def test_missing(self) -> None:
        unf = self._unf_of_single(b"\x00\x00\x00")
        assert unf == "UNF:6:cJ6AyISHokEeHuTfufIqhg=="

    def test_accented_string(self) -> None:
        unf = self._unf_of_single(b"p\xc3\xa5 F\xc3\xa6r\xc3\xb8erne\n\x00")
        assert unf == "UNF:6:KHM6bKVaVaxWDDsmyerfDA=="

    def test_long_string(self) -> None:
        long_str = (
            "A quite long character string, so long that the number of "
            "characters in it happens to be more than the default cutoff "
            "limit of 1"
        )
        # 128 chars + terminator
        normalized = long_str.encode("utf-8") + b"\n\x00"
        unf = self._unf_of_single(normalized)
        assert unf == "UNF:6:/BoSlfcIlsmQ+GHu5gxwEw=="


# ---------------------------------------------------------------
# Column-level UNF via unf_column()
# ---------------------------------------------------------------


class TestUNFColumn:
    """Test unf_column with Polars Series."""

    def test_numeric_column(self) -> None:
        series = pl.Series("test", [0])
        result = unf_column(series)
        assert result == "UNF:6:YUvj33xEHnzirIHQyZaHow=="

    def test_string_column(self) -> None:
        series = pl.Series("test", ["A character String"])
        result = unf_column(series)
        assert result == "UNF:6:FYqU7uBl885eHMbpco1ooA=="

    def test_boolean_true_column(self) -> None:
        # TRUE treated as 1 -> same UNF as integer 1
        series = pl.Series("test", [True])
        result = unf_column(series)
        assert result == "UNF:6:tv3XYCv524AfmlFyVOhuZg=="

    def test_boolean_false_column(self) -> None:
        # FALSE treated as 0 -> same UNF as integer 0
        series = pl.Series("test", [False])
        result = unf_column(series)
        assert result == "UNF:6:YUvj33xEHnzirIHQyZaHow=="

    def test_column_with_missing(self) -> None:
        """Vector: {1.23456789, <MISSING>, 0} from the spec example."""
        series = pl.Series("test", [1.23456789, None, 0.0])
        result = unf_column(series)
        assert result == "UNF:6:Do5dfAoOOFt4FSj0JcByEw=="


# ---------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------


class TestParameters:
    def test_defaults(self) -> None:
        p = UNFParameters()
        assert p.is_default
        assert p.header == "UNF:6:"

    def test_non_default_header(self) -> None:
        p = UNFParameters(digits=9)
        assert not p.is_default
        assert p.header == "UNF:6:N9:"

    def test_multiple_non_defaults(self) -> None:
        p = UNFParameters(digits=9, hash_bits=256)
        assert p.header == "UNF:6:N9,H256:"

    def test_invalid_hash_bits(self) -> None:
        with pytest.raises(ValueError, match="hash_bits must be one of"):
            UNFParameters(hash_bits=64)

    def test_non_default_precision_example(self) -> None:
        """From the spec: 1.23456789 at N=9 -> UNF:6:N9:IKw+l4ywdwsJeDze8dplJA=="""
        params = UNFParameters(digits=9)
        series = pl.Series("test", [1.23456789])
        result = unf_column(series, params)
        assert result == "UNF:6:N9:IKw+l4ywdwsJeDze8dplJA=="


# ---------------------------------------------------------------
# §Ia.5a – Date normalization
# ---------------------------------------------------------------


class TestNormalizeDate:
    def test_simple_date(self) -> None:
        result = normalize_date(date(2014, 1, 13))
        assert result == b"2014-01-13\n\x00"

    def test_date_zero_padded(self) -> None:
        result = normalize_date(date(2012, 6, 10))
        assert result == b"2012-06-10\n\x00"

    def test_date_year_padding(self) -> None:
        """Years before 1000 should be zero-padded to 4 digits."""
        result = normalize_date(date(99, 3, 5))
        assert result == b"0099-03-05\n\x00"


# ---------------------------------------------------------------
# §Ia.5b – Time normalization
# ---------------------------------------------------------------


class TestNormalizeTime:
    def test_simple_time(self) -> None:
        result = normalize_time(time(20, 47, 18))
        assert result == b"20:47:18\n\x00"

    def test_time_zero_padded(self) -> None:
        result = normalize_time(time(2, 5, 3))
        assert result == b"02:05:03\n\x00"

    def test_time_with_fractional_seconds(self) -> None:
        # 0.5 seconds = 500000 microseconds
        result = normalize_time(time(14, 29, 0, 500000))
        assert result == b"14:29:00.5\n\x00"

    def test_time_fractional_no_trailing_zeros(self) -> None:
        # 123400 microseconds -> .1234 (trailing zeros stripped)
        result = normalize_time(time(10, 0, 0, 123400))
        assert result == b"10:00:00.1234\n\x00"

    def test_time_fractional_full_precision(self) -> None:
        # 123456 microseconds -> .123456
        result = normalize_time(time(10, 0, 0, 123456))
        assert result == b"10:00:00.123456\n\x00"

    def test_time_no_fractional_when_zero(self) -> None:
        result = normalize_time(time(0, 0, 0))
        assert result == b"00:00:00\n\x00"

    def test_time_with_utc_timezone(self) -> None:
        t = time(16, 51, 5, tzinfo=UTC)
        result = normalize_time(t)
        assert result == b"16:51:05Z\n\x00"

    def test_time_with_non_utc_timezone(self) -> None:
        """EST is UTC-5, so 12:51:05 EST -> 17:51:05 UTC."""
        est = timezone(timedelta(hours=-5))
        t = time(12, 51, 5, tzinfo=est)
        result = normalize_time(t)
        assert result == b"17:51:05Z\n\x00"


# ---------------------------------------------------------------
# §Ia.5c – DateTime normalization
# ---------------------------------------------------------------


class TestNormalizeDatetime:
    def test_naive_datetime(self) -> None:
        """Spec example: Mon Jan 13 20:47:18 2014 (no TZ)."""
        dt = datetime(2014, 1, 13, 20, 47, 18)
        result = normalize_datetime(dt)
        assert result == b"2014-01-13T20:47:18\n\x00"

    def test_timezone_aware_datetime(self) -> None:
        """Spec example: Mon Jan 13 20:47:18 EST 2014 -> 2014-01-14T01:47:18Z.

        EST is UTC-5. Note the date rolls over to Jan 14.
        """
        est = timezone(timedelta(hours=-5))
        dt = datetime(2014, 1, 13, 20, 47, 18, tzinfo=est)
        result = normalize_datetime(dt)
        assert result == b"2014-01-14T01:47:18Z\n\x00"

    def test_utc_datetime(self) -> None:
        dt = datetime(2012, 6, 10, 14, 29, 0, tzinfo=UTC)
        result = normalize_datetime(dt)
        assert result == b"2012-06-10T14:29:00Z\n\x00"

    def test_datetime_with_fractional_seconds(self) -> None:
        dt = datetime(2014, 8, 22, 12, 51, 5, 500000)
        result = normalize_datetime(dt)
        assert result == b"2014-08-22T12:51:05.5\n\x00"

    def test_edt_datetime(self) -> None:
        """Spec example: Fri Aug 22 12:51:05 EDT 2014 -> 2014-08-22T16:51:05Z.

        EDT is UTC-4.
        """
        edt = timezone(timedelta(hours=-4))
        dt = datetime(2014, 8, 22, 12, 51, 5, tzinfo=edt)
        result = normalize_datetime(dt)
        assert result == b"2014-08-22T16:51:05Z\n\x00"


# ---------------------------------------------------------------
# §Ia.5d – Duration normalization
# ---------------------------------------------------------------


class TestNormalizeDuration:
    def test_one_hour(self) -> None:
        """1 hour = 3600 seconds -> +3.6e+3"""
        result = normalize_duration(timedelta(hours=1))
        assert result == b"+3.6e+3\n\x00"

    def test_zero_duration(self) -> None:
        result = normalize_duration(timedelta(0))
        assert result == b"+0.e+\n\x00"

    def test_fractional_seconds(self) -> None:
        """1.5 seconds -> +1.5e+"""
        result = normalize_duration(timedelta(seconds=1.5))
        assert result == b"+1.5e+\n\x00"


# ---------------------------------------------------------------
# §Ia.5 – Official UNF test vectors for dates/times
# ---------------------------------------------------------------


class TestDateTimeUNFHash:
    """Test UNF hashing of date/time values against official test vectors."""

    params = UNFParameters()

    def _unf_of_single(self, normalized_bytes: bytes) -> str:
        return compute_unf_hash(normalized_bytes, self.params)

    def test_datetime_no_timezone(self) -> None:
        """Mon Jan 13 20:47:18 2014 -> UNF:6:eaMxex5EHi2LunomVc0SDw=="""
        normalized = b"2014-01-13T20:47:18\n\x00"
        unf = self._unf_of_single(normalized)
        assert unf == "UNF:6:eaMxex5EHi2LunomVc0SDw=="

    def test_datetime_with_est(self) -> None:
        """Mon Jan 13 20:47:18 EST 2014 -> UNF:6:1Pku/Z/EIRtmpdEepAb1MA=="""
        normalized = b"2014-01-14T01:47:18Z\n\x00"
        unf = self._unf_of_single(normalized)
        assert unf == "UNF:6:1Pku/Z/EIRtmpdEepAb1MA=="


# ---------------------------------------------------------------
# §Ia.5 – Polars column integration for dates/times
# ---------------------------------------------------------------


class TestDateTimeColumns:
    """Test unf_column with Polars date/time Series."""

    def test_date_column(self) -> None:
        series = pl.Series("d", [date(2014, 1, 13)])
        result = unf_column(series)
        # Should produce UNF from "2014-01-13\n\0"
        expected = compute_unf_hash(b"2014-01-13\n\x00")
        assert result == expected

    def test_datetime_naive_column(self) -> None:
        """Polars Datetime without timezone should produce naive normalization."""
        series = pl.Series("dt", [datetime(2014, 1, 13, 20, 47, 18)])
        result = unf_column(series)
        expected = compute_unf_hash(b"2014-01-13T20:47:18\n\x00")
        assert result == expected

    def test_datetime_utc_column(self) -> None:
        """Polars Datetime with UTC timezone should produce Z-suffixed normalization."""
        series = pl.Series("dt", [datetime(2014, 1, 13, 20, 47, 18)]).cast(
            pl.Datetime("us", "UTC")
        )
        result = unf_column(series)
        expected = compute_unf_hash(b"2014-01-13T20:47:18Z\n\x00")
        assert result == expected

    def test_datetime_est_column(self) -> None:
        """Polars Datetime with US/Eastern timezone.

        2014-01-13 20:47:18 EST -> 2014-01-14 01:47:18 UTC.
        Matches official test vector UNF:6:1Pku/Z/EIRtmpdEepAb1MA==
        """
        # Create a UTC datetime that represents 20:47:18 EST (= 01:47:18+1 UTC)
        est = timezone(timedelta(hours=-5))
        dt_est = datetime(2014, 1, 13, 20, 47, 18, tzinfo=est)
        dt_utc = dt_est.astimezone(UTC)

        series = pl.Series("dt", [dt_utc]).cast(pl.Datetime("us", "UTC"))
        result = unf_column(series)
        assert result == "UNF:6:1Pku/Z/EIRtmpdEepAb1MA=="

    def test_time_column(self) -> None:
        series = pl.Series("t", [time(14, 29, 0)])
        result = unf_column(series)
        expected = compute_unf_hash(b"14:29:00\n\x00")
        assert result == expected

    def test_duration_column(self) -> None:
        series = pl.Series("dur", [timedelta(hours=1)])
        result = unf_column(series)
        # 3600 seconds -> "+3.6e+3\n\0"
        expected = compute_unf_hash(b"+3.6e+3\n\x00")
        assert result == expected

    def test_datetime_column_with_missing(self) -> None:
        """Datetime column with a null value."""
        series = pl.Series("dt", [datetime(2014, 1, 13, 20, 47, 18), None])
        result = unf_column(series)
        expected = compute_unf_hash(b"2014-01-13T20:47:18\n\x00" + b"\x00\x00\x00")
        assert result == expected
