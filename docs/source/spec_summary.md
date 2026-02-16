# UNF v6 Specification Summary

The **Universal Number Fingerprint (UNF)** is a system-independent digital signature for data objects. This page summarizes the normalization rules for version 6 of the specification.

## High-Level Process

1.  **Normalize**: Each value in a data vector is converted to a canonical string representation.
2.  **Terminate**: Each non-missing normalized string is terminated with a newline (`\n`) and a null byte (`\000`).
3.  **Hash**: All terminated strings are concatenated, and a SHA-256 hash is computed.
4.  **Truncate**: The resulting hash is truncated to $H$ bits (default 128).
5.  **Encode**: The bits are Base64 encoded and prepended with a versioned header (e.g., `UNF:6:`).

## Normalization Rules

### Numeric Values (§Ia.1)

*   **Rounding**: Values are rounded to $N$ significant digits (default 7) using IEEE 754 "round towards nearest, ties to even".
*   **Format**: `[sign][digit].[digits]e[sign][exponent]`
*   **Special Cases**:
    *   Positive Zero: `+0.e+`
    *   Negative Zero: `-0.e+`
    *   Infinity: `+inf`, `-inf`
    *   Not-a-Number: `+nan`

### Character Strings (§Ia.2)

*   **Encoding**: UTF-8.
*   **Truncation**: Truncated to $X$ characters (default 128).
*   **Terminator**: Appended after truncation.

### Boolean Values (§Ia.3)

*   Treated as numeric `0` (False) or `1` (True).

### Bit Fields (§Ia.4)

*   Converted to big-endian form.
*   Leading zero bits are truncated.
*   Aligned to a byte boundary.
*   Base64 encoded.

### Date and Time (§Ia.5)

*   **Dates**: `YYYY-MM-DD` (partial dates like `YYYY` or `YYYY-MM` allowed).
*   **Time**: `hh:mm:ss.fffff`. Must be UTC (appended with `Z`). Fractional seconds `fffff` have no trailing zeros.
*   **Datetime**: Concatenation of Date + `T` + Time.

### Missing Values (§Ia.6)

*   Encoded as exactly three null bytes: `\000\000\000`.
*   **Crucial**: Missing values are **not** terminated with a newline or null byte.

## Hierarchical Composition

### Data Frames (§IIa)

To calculate the UNF of a dataset with multiple columns:
1.  Calculate the UNF of each individual column.
2.  Sort the printable UNF strings in POSIX locale order.
3.  Treat the sorted UNF strings as a vector of character strings and calculate a new UNF.

### Multi-file Datasets (§IIb)

1.  Calculate the UNF of each file.
2.  Combine them using the same sorting and hashing logic used for Data Frames.

## Optional Parameters

Non-default parameters are recorded in the UNF header:
*   `N`: Significant digits (e.g., `N9`).
*   `X`: String truncation length (e.g., `X256`).
*   `H`: Hash truncation bits (e.g., `H256`).
*   `R1`: Use truncation instead of rounding for numbers.
