# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-03-09

- Added native support for statistical file formats: SAS (.sas7bdat, .xpt), Stata (.dta), and SPSS (.sav, .zsav).
- Implemented optional leading zero detection in CSV files to preserve code lists as strings.
- **Alignment with Java Dataverse implementation**:
    - Stripped `UNF:6:` headers from column UNFs before combination (aggregation).
    - Added "Dataverse-parity" mode for null handling (treating empty CSV fields as empty strings).
- Added `--leading-zeros` and `--null-as-strings` CLI flags.
- Enhanced JSON report schema with a new `metadata.options` field for full run traceability.
- Refactored internal schema handling and deduplicated Polars type override logic.
- Modernized internal Polars field types (transitioned from `Utf8` to `String`).
- Added comprehensive CLI tests for date parsing and leading zero behaviors.

## [0.1.0] - 2024-03-24

- Initial release of `dartfx-unf`.
- Full compliance with UNF v6 specification.
- High-performance Polars-based engine for CSV and Parquet files.
- Out-of-core streaming for large datasets.
- Dataset-level hashing support.
- Professional CLI with JSON report output.
