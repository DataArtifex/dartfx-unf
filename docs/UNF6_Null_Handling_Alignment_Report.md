# UNF Discrepancy Analysis: Null Handling in String Columns

## Executive Summary
A discrepancy was identified between the `dartfx-unf` (Python) and `UNF-dataverse` (Java) implementations when processing CSV files containing null values (empty fields) in string columns. While both tools aim to follow the UNF v6 specification, their underlying CSV parsing libraries handle empty fields differently, leading to divergent fingerprints.

`dartfx-unf` has been updated to provide a "Dataverse-parity" mode via the `--null-as-string` option, which aligns the Python implementation's behavior with the canonical Java one.

## Root Cause Analysis

### 1. CSV Parsing Differences
The primary cause is found in the CSV parsing layer of each implementation:

*   **Java (UNF-dataverse)**: Uses a simplified parser that splits lines by a delimiter (e.g., `,`). An empty field between commas (`,,`) results in a literal empty string (`""`) in memory.
*   **Python (dartfx-unf/Polars)**: Uses an industrial-grade CSV parser that distinguishes between an empty field (`,,`) and a literal string "null". Empty fields are correctly interpreted as `null` (missing values).

### 2. UNF Specification vs. Implementation
The UNF v6 specification defines two distinct treatments:
*   **Missing Values (§Ia.6)**: Normalized to three null bytes (`\x00\x00\x00`).
*   **Empty Strings (§Ia.2)**: Normalized to a newline followed by a null byte (`\x0a\x00`).

The Java implementation treats empty CSV fields as **non-missing empty strings**, thereby hashing them as `\x0a\x00`.
The Python implementation (originally) treated them as **missing values**, hashing them as `\x00\x00\x00`.

## Verification Results: `pub1225.csv` (NOC_43 Column)

Testing on the user-provided `pub1225.csv` dataset confirmed this finding:

| Implementation / Mode | Hypothesis | NOC_43 UNF Result | Match |
| :--- | :--- | :--- | :--- |
| **Python (Original)** | Treat empty fields as `null` | `UNF:6:fEEKAU0CABq1/ld+oGJlfA==` | Python baseline |
| **Java (Dataverse)** | Treat empty fields as `""` | `UNF:6:SuBRM0rMx1ZED9kCACABCg==` | Java baseline |
| **Python (Updated Parity)** | Treat `null` as `""` | `UNF:6:SuBRM0rMx1ZED9kCACABCg==` | **MATCH** |

*Note: Achieving parity also required reading the column as a string to preserve leading zeros (e.g., `08` vs `8`), which Java does by default when inference fails due to empty fields.*

## Resolution in `dartfx-unf`

The `null-as-string` handling mode in `dartfx-unf` (activated by `--null-as-string` on the CLI) has been enhanced to:
1.  **Force String Casting**: Identify columns with nulls and treat them as string columns.
2.  **Parity Normalization**: Treat `null` values in these columns as empty strings (`\n\x00`) instead of missing values (`\x00\x00\x00`).

### Recommended Usage for Dataverse Alignment
To ensure maximum compatibility with the Dataverse Java implementation, use the following flags:
```bash
dartfx-unf /path/to/data.csv --null-as-string --scan-length -1
```
*   `--null-as-string`: Activates Dataverse-compatible null and string handling.
*   `--scan-length -1`: Ensures the entire file is scanned for nulls and leading zeros, preventing incorrect numeric inference.

## Conclusion
The discrepancy was not a failure of the UNF hashing logic itself, but rather a difference in the interpretation of "missingness" in CSV files. By providing a dedicated alignment mode, `dartfx-unf` now ensures consistency with the Dataverse ecosystem while remaining spec-compliant in its default operation.
