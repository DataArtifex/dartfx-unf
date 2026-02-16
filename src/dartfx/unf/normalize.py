# SPDX-FileCopyrightText: 2024-present kulnor <pascal@codata.org>
#
# SPDX-License-Identifier: MIT

"""Normalization of individual values according to UNF v6 specification.

This module handles section Ia of the specification:
- Numeric normalization (Ia.1)
- String normalization (Ia.2)
- Boolean normalization (Ia.3)
- Date/Time normalization (Ia.5)
- Missing value encoding (Ia.6)
"""

from __future__ import annotations

import base64
import math
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_EVEN, Decimal

# Sentinel bytes for missing values (3 null bytes, no terminator).
MISSING_VALUE = b"\x00\x00\x00"

# End-of-value terminator: newline + null byte.
VALUE_TERMINATOR = b"\n\x00"


def normalize_numeric(
    value: float | int, digits: int = 7, *, truncate: bool = False
) -> bytes:
    """Normalize a single numeric value per UNF v6 spec §Ia.1.

    Parameters
    ----------
    value : float or int
        The numeric value to normalize.
    digits : int
        Number of significant digits (``N``).
    truncate : bool
        If True, truncate instead of rounding (``R1`` mode).

    Returns
    -------
    bytes
        The normalized byte representation including the terminator.
    """
    # Handle NaN
    if isinstance(value, float) and math.isnan(value):
        return b"+nan" + VALUE_TERMINATOR

    # Handle Infinity
    if isinstance(value, float) and math.isinf(value):
        if value > 0:
            return b"+inf" + VALUE_TERMINATOR
        return b"-inf" + VALUE_TERMINATOR

    # Handle zero (positive and negative)
    if value == 0:
        # Detect negative zero
        if isinstance(value, float) and math.copysign(1.0, value) < 0:
            return b"-0.e+" + VALUE_TERMINATOR
        return b"+0.e+" + VALUE_TERMINATOR

    # Use Decimal for precise significant-digit rounding
    d = Decimal(str(value))

    if truncate:
        # R1 mode: truncate to N significant digits
        # Quantize towards zero
        d = d.normalize()
        sign, coefficient, exponent = d.as_tuple()
        coeff_str = "".join(str(c) for c in coefficient)
        if len(coeff_str) > digits:
            # Calculate the new exponent for the truncated number
            # The original exponent is for the full coefficient.
            # If we truncate, the effective exponent changes.
            # Example: 12345E-2, digits=3 -> 123E0
            # original: coeff=(1,2,3,4,5), exponent=-2, len=5
            # new coeff_str = "123", new len=3
            # sci_exp = exponent + len(coeff) - 1 = -2 + 5 - 1 = 2
            # new sci_exp = exponent + len(new_coeff) - 1
            # new exponent = new_sci_exp - len(new_coeff) + 1
            # new exponent = (exponent + len(coefficient) - 1) - digits + 1
            #              = exponent + len(coefficient) - digits
            new_exponent = exponent + len(coefficient) - digits
            d = Decimal(
                ("-" if sign else "") + coeff_str[:digits] + "E" + str(new_exponent)
            )
            d = d.normalize()  # Re-normalize after manual truncation
    else:
        # Default: IEEE 754 "round towards nearest, ties to even"
        d = d.normalize()
        sign_d, coefficient, exponent = d.as_tuple()
        num_digits = len(coefficient)
        if num_digits > digits:
            # Round to N significant digits
            shift = num_digits - digits
            # quantize targets the exponent of the argument
            # e.g., to round 12345 to 3 digits, shift=2.
            # original exponent for 12345 is 0 (12345E0).
            # We want to round to 12300, which is 123E2.
            # The quantizer should be 1E2.
            # exponent + shift = 0 + 2 = 2. So "1e2".
            quant = Decimal("1e" + str(exponent + shift))
            d = d.quantize(quant, rounding=ROUND_HALF_EVEN)
            d = d.normalize()

    # Convert to our exponential format
    return _format_exponential(d) + VALUE_TERMINATOR


def _format_exponential(d: Decimal) -> bytes:
    """Format a Decimal into UNF exponential notation.

    Format: ``[+-]D.DDD...e[+-]EEE``

    Examples:
        1      -> +1.e+
        -300   -> -3.e+2
        0.00073 -> +7.3e-4
    """
    sign_d, coefficient, exponent = d.normalize().as_tuple()

    if not coefficient:
        # Shouldn't reach here (zero handled upstream), but be safe.
        sign_char = "-" if sign_d else "+"
        return (sign_char + "0.e+").encode("ascii")

    sign_char = "-" if sign_d else "+"

    coeff_str = "".join(str(c) for c in coefficient)

    # The exponent in UNF notation:
    # Decimal("3E+2") means 300, tuple gives exponent=2, coeff=(3,)
    # We want "+3.e+2"
    # Decimal("3.1415") normalized gives coeff=(3,1,4,1,5), exponent=-4
    # scientific exponent = exponent + len(coeff) - 1
    sci_exp = exponent + len(coeff_str) - 1

    # Build mantissa: leading digit, then "." then remaining digits
    if len(coeff_str) == 1:
        mantissa = coeff_str[0] + "."
    else:
        mantissa = coeff_str[0] + "." + coeff_str[1:]
        # Remove trailing zeros from fractional part
        mantissa = mantissa.rstrip("0")
        if mantissa.endswith("."):
            pass  # Keep the trailing dot

    # Build exponent part
    if sci_exp >= 0:
        exp_part = "e+" + (str(sci_exp) if sci_exp != 0 else "")
    else:
        exp_part = "e" + str(sci_exp)

    return (sign_char + mantissa + exp_part).encode("ascii")


def normalize_string(value: str, max_chars: int = 128) -> bytes:
    """Normalize a character string per UNF v6 spec §Ia.2.

    Encode as UTF-8, truncate to ``max_chars`` characters, then add
    the newline + null terminator.

    Parameters
    ----------
    value : str
        The string value to normalize.
    max_chars : int
        Maximum number of characters to keep (``X``).

    Returns
    -------
    bytes
        The normalized byte representation.
    """
    truncated = value[:max_chars]
    return truncated.encode("utf-8") + VALUE_TERMINATOR


def normalize_boolean(value: bool) -> bytes:
    """Normalize a boolean value per UNF v6 spec §Ia.3.

    Booleans are treated as numeric 1 (True) or 0 (False).
    """
    if value:
        return b"+1.e+" + VALUE_TERMINATOR
    return b"+0.e+" + VALUE_TERMINATOR


def normalize_bit_field(value: bytes) -> bytes:
    """Normalize a bit field value per UNF v6 spec §Ia.4.

    Normalization steps:
    1. Convert to big-endian form (implicit in binary input).
    2. Truncate leading zero bits.
    3. Align to a byte boundary (minimise bytes needed).
    4. Base64 encode the result.
    5. Append terminator.
    """
    # 0. Handle empty
    if not value:
        return base64.b64encode(b"") + VALUE_TERMINATOR

    # 1-3. Big-endian integer conversion and minimal byte retrieval
    # handles steps 1 (big-endian), 2 (truncate leading zeros),
    # and 3 (align to byte boundary) by getting the minimal byte
    # representation of the underlying integer.
    i = int.from_bytes(value, "big")
    if i == 0:
        minimal_bytes = b""
    else:
        num_bytes = (i.bit_length() + 7) // 8
        minimal_bytes = i.to_bytes(num_bytes, "big")

    # 4. Base64 encode
    b64 = base64.b64encode(minimal_bytes)

    # 5. Append terminator
    return b64 + VALUE_TERMINATOR


# ---------------------------------------------------------------------------
# §Ia.5 – Date, Time, and Interval normalization
# ---------------------------------------------------------------------------


def _format_time_component(t: time) -> str:
    """Format a time value per UNF v6 spec §Ia.5b.

    Format: ``hh:mm:ss[.fffff]``

    - ``hh``, ``mm``, ``ss`` are 2-digit, zero-padded.
    - Fractional seconds contain no trailing zeros; omitted if zero.
    """
    base = f"{t.hour:02d}:{t.minute:02d}:{t.second:02d}"

    if t.microsecond:
        # Format microseconds as up to 6 digits, strip trailing zeros
        frac = f"{t.microsecond:06d}".rstrip("0")
        return f"{base}.{frac}"

    return base


def normalize_date(value: date) -> bytes:
    """Normalize a date value per UNF v6 spec §Ia.5a.

    Format: ``YYYY-MM-DD``, zero-padded.

    Parameters
    ----------
    value : datetime.date
        The date value to normalize.

    Returns
    -------
    bytes
        The normalized byte representation including the terminator.
    """
    formatted = f"{value.year:04d}-{value.month:02d}-{value.day:02d}"
    return formatted.encode("utf-8") + VALUE_TERMINATOR


def normalize_time(value: time) -> bytes:
    """Normalize a time value per UNF v6 spec §Ia.5b.

    Format: ``hh:mm:ss[.fffff][Z]``

    If the time has timezone information, it is converted to UTC and
    a ``Z`` suffix is appended.

    Parameters
    ----------
    value : datetime.time
        The time value to normalize.

    Returns
    -------
    bytes
        The normalized byte representation including the terminator.
    """
    if value.tzinfo is not None:
        # Convert to UTC: create a dummy datetime to perform the conversion
        dummy_dt = datetime(
            2000,
            1,
            1,
            value.hour,
            value.minute,
            value.second,
            value.microsecond,
            tzinfo=value.tzinfo,
        )
        utc_dt = dummy_dt.astimezone(UTC)
        formatted = _format_time_component(utc_dt.time()) + "Z"
    else:
        formatted = _format_time_component(value)

    return formatted.encode("utf-8") + VALUE_TERMINATOR


def normalize_datetime(value: datetime) -> bytes:
    """Normalize a combined date+time value per UNF v6 spec §Ia.5c.

    Format: ``YYYY-MM-DDThh:mm:ss[.fffff][Z]``

    If the datetime is timezone-aware, it is converted to UTC and a
    ``Z`` suffix is appended. Partial dates are prohibited in combined
    date and time values.

    Parameters
    ----------
    value : datetime.datetime
        The datetime value to normalize.

    Returns
    -------
    bytes
        The normalized byte representation including the terminator.
    """
    if value.tzinfo is not None:
        # Convert to UTC
        utc_dt = value.astimezone(UTC)
        date_part = f"{utc_dt.year:04d}-{utc_dt.month:02d}-{utc_dt.day:02d}"
        time_part = _format_time_component(utc_dt.time()) + "Z"
    else:
        date_part = f"{value.year:04d}-{value.month:02d}-{value.day:02d}"
        time_part = _format_time_component(value.time())

    formatted = f"{date_part}T{time_part}"
    return formatted.encode("utf-8") + VALUE_TERMINATOR


def normalize_duration(value: timedelta) -> bytes:
    """Normalize a duration/interval value per UNF v6 spec §Ia.5d.

    Durations are represented as the total number of seconds,
    normalized as a numeric value. This is a pragmatic interpretation
    since the spec dropped formal duration support but Polars Duration
    columns still need handling.

    Parameters
    ----------
    value : datetime.timedelta
        The duration value to normalize.

    Returns
    -------
    bytes
        The normalized byte representation including the terminator.
    """
    total_seconds = value.total_seconds()
    return normalize_numeric(total_seconds)


def normalize_missing() -> bytes:
    """Return the missing value representation per UNF v6 spec §Ia.6.

    Missing values are encoded as 3 null bytes with NO terminator.
    """
    return MISSING_VALUE
