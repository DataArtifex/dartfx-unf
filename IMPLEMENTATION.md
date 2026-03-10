# Implementation Notes

This document describes the architecture, current status, and planned next steps for `dartfx-unf`.

> [!WARNING]
> **Prototype Status**: This project is currently a **prototype**. Full alignment on the UNF v6 specification and the canonical Java Dataverse implementation is a work in progress. It is intended for **evaluation purposes only** and is not yet suitable for production environments.

## Architecture

The package follows a layered design that separates concerns cleanly, making it usable as a **library**, a **CLI tool**, or embedded in an **API/MCP server**.

```
src/dartfx/unf/
├── __init__.py       # Public API surface
├── __about__.py      # Version string (single source of truth)
├── parameters.py     # UNFParameters – frozen dataclass for N, X, H, R1
├── normalize.py      # Value-level normalization (spec §Ia)
├── hasher.py         # SHA-256 hashing, incremental + batch (spec §Ib, §II)
├── memory.py         # System memory detection & streaming heuristic
├── core.py           # High-level API: unf_column, unf_file, unf_dataset
├── report.py         # UNFReport dataclass with JSON serialisation
├── unf6_schema.json  # Bundled JSON schema for output validation
└── cli.py            # CLI entry point (registered as `dartfx-unf`)
```

### Data Flow

```
Input File (.csv / .parquet)
    │
    ├─── small file ──► in-memory (pl.read_csv / pl.read_parquet)
    │                      │
    └─── large file ──► streaming (scan_csv.collect_batches / pyarrow.iter_batches)
                           │
    ┌──────────────────────────────────────────┐
    │  core.unf_file()                         │
    │  ├─ per-column SHA-256 hashers           │
    │  ├─ for each batch:                      │
    │  │   └─ for each column:                 │
    │  │       ├─ normalize values             │   normalize.py (§Ia)
    │  │       └─ hasher.update(bytes)         │   incremental SHA-256
    │  ├─ finalize each column hash → UNF      │   hasher.finalize_hash (§Ib)
    │  └─ combine column UNFs                  │   hasher.combine_unfs (§IIa)
    └──────────────────────────────────────────┘
        │
        ▼
      UNFReport (→ JSON, dict, or plain UNF string)
```

### Design Decisions

1. **Library-first API.** The core functions (`unf_column`, `unf_file`, `unf_dataset`) accept standard Python and Polars types and return structured results. This makes integration into FastAPI, Flask, MCP servers, or Jupyter notebooks straightforward.

2. **`UNFParameters` as a frozen dataclass.** Calculation parameters are immutable and validated at construction. The `header` property auto-generates the correct UNF prefix (e.g. `UNF:6:N9,H256:`).

3. **`Decimal`-based rounding.** Python's `decimal` module with `ROUND_HALF_EVEN` is used to implement the IEEE 754 "round towards nearest, ties to even" requirement. This avoids floating-point surprises that would occur with direct `round()` calls.

4. **Separation of normalization and hashing.** `normalize.py` produces raw bytes for individual values. `hasher.py` handles SHA-256, truncation, base64 encoding, and the recursive combination algorithm. This separation makes each layer independently testable.

5. **JSON report schema.** The `UNFReport` object serialises to JSON matching the bundled `unf6_schema.json`, providing full traceability from dataset → file → column.

6. **Memory-aware streaming.** `memory.py` detects available system memory (Linux `/proc/meminfo`, macOS `os.sysconf`, Windows `kernel32`). Files larger than 25% of available memory automatically switch to streaming mode, which uses incremental SHA-256 hashers to achieve O(batch_size) memory usage regardless of total file size.

7. **Canonical Alignment.** A primary design constraint is parity with the [Java Dataverse implementation](https://github.com/IQSS/UNF). This ensures that fingerprints computed by `dartfx-unf` match those already residing in data repositories.

8. **Transparency & Options.** When the specification is ambiguous or allows for multiple valid calculation paths, explicit options are provided (e.g., `detect_leading_zeros`). These settings are preserved in the JSON report's `metadata.options` field for full auditability.

## Current Status

### Implemented (✅)

| Spec Section | Feature | Notes |
|---|---|---|
| §Ia.1 | Numeric normalization | IEEE 754 ties-to-even via `Decimal`. Handles zero, negative zero, NaN, ±Inf. |
| §Ia.2 | String normalization | UTF-8 encoding with truncation to X characters. |
| §Ia.3 | Boolean normalization | Mapped to numeric 0/1. |
| §Ia.4 | Bit field normalization | Big-endian → truncate → align → Base64. |
| §Ia.5 | Date/Time normalization | Dates, times, datetimes (with UTC conversion), and durations. |
| §Ia.6 | Missing values | 3 null bytes, no terminator. |
| §Ib | Vector UNF | Incremental SHA-256 → truncate to H bits → base64 → header. |
| §IIa | File UNF | Column UNFs sorted in POSIX locale order, then combined. |
| §IIb | Dataset UNF | File UNFs sorted and combined. |
| Footnote | Non-default parameters | N, X, H, R1 embedded in header string. |
| — | CLI | `dartfx-unf` command with `--quiet`, `--output`, `--verbose`, `--validate`. |
| — | JSON report | Structured output matching `docs/unf6_schema.json` with schema validation. |
| — | Schema specification | JSON Schema-based type override for CSV data. Supports file paths, inline JSON, and Python dicts. Ensures consistent type handling across systems. |
| — | Performance | Memory-aware streaming, vectorized normalization, and parallel column/file processing. |
| — | API | Helpers for DataFrames, bytes, and file-like streams. |
| — | Statistical Formats | Native support for SAS (.sas7bdat, .xpt), Stata (.dta), and SPSS (.sav, .zsav). |
| — | Code Preservation | Optional leading zero detection to preserve CSV code lists as strings. |
| — | Null Handling | Options for `null-as-string` matching Dataverse Java behavior or `null-as-null` (default). |
| — | Traceability | `metadata.options` in JSON reports to record all calculation settings. |
| — | Benchmarking | Comprehensive macro-benchmark suite with CI integration. |
| — | Documentation | Sphinx site with Usage Guide, API Reference, and Spec Summary. |
| — | QA | Pre-commit hooks with `ruff`, `ruff-format`, and automated linting. |
| — | Date/DateTime Format Support | JSON Schema `format` property and `oneOf` for explicit date/datetime parsing with multiple format support. |

### Validated Against Official Test Vectors

All test cases from the [IQSS UNF reference examples](https://raw.githubusercontent.com/IQSS/UNF/master/doc/unf_examples.txt) pass. Total test count: **100** (71 UNF spec + 29 streaming/performance/edge-case equivalence).

## Recent Performance & Usability Improvements

The following features have been successfully integrated:

1. **Memory-Aware Streaming**: `memory.py` detects available RAM (Linux, macOS, Windows) and automatically switches to O(batch_size) streaming for large files.
2. **Vectorized Normalization**: Boolean, String, and Date types use Polars native Rust-based expressions for high-speed formatting.
3. **Parallel Processing**: Both column-level hashing (within a file) and file-level processing (within a dataset) are parallelized via thread pools.
4. **Programmatic Flexbility**: Added `unf_dataframe`, `unf_from_bytes`, and `unf_from_stream` to allow UNF calculation without intermediate disk I/O.
5. **Human-Friendly CLI**: Added `-v/--verbose` for summary tables and `--validate` to ensure JSON output correctness.
6. **Macro-Benchmarking & CI**: Automated performance tracking with `benchmarks/macro.py` measuring throughput (~160k rows/s) and memory efficiency, integrated into GitHub Actions.
7. **Spec Completeness**: Added Bit Field normalization (§Ia.4) and fixed critical precision bugs in `Decimal` quantization for integers exceeding $2^{60}$.
8. **Automatic Date Parsing**: Enabled `parse_dates=True` by default for CSV reading, improving the default UNF accuracy for temporal data without requiring explicit schema definitions.
9. **Statistical Format Support**: Integrated `pyreadstat` for native processing of SAS, Stata, and SPSS files, ensuring consistency between statistical packages and raw formats.
10. **Leading Zero Detection**: Implemented a "code list" protection heuristic that automatically identifies and preserves leading zeros in CSV columns as strings.
11. **Settings Traceability**: Added an `options` field to JSON reports, recording every parameter (streaming, batch size, etc.) used for the run.
12. **Null Handling**: Added support for configuring null handling (`--null-as-string` and `--null-as-null`) to perfectly align outputs with the canonical Java Dataverse implementation.


## Roadmap & Phases

### Phase 2: Interoperability & Extensions (Current)

- [x] **Statistical Format Support.** Integrated `pyreadstat` for SAS, Stata, and SPSS.
- [ ] **JSON/XML Support.** Direct normalization for semi-structured data formats.
- [ ] **CLI Polish.** Add progress bars for massive streaming operations.
- [ ] **R Interoperability.** Native R package or binding for verification across R/Python.

### Phase 3: Distribution & Stability

- [ ] **PyPI Publishing.** Set up GitHub Actions workflow for automated releases to PyPI.
- [ ] **Test Coverage Automation.** Integrated `coverage.py` reports into CI/CD pipeline.
- [ ] **Type Safety.** Ensure `mypy --strict` passes across the entire codebase.
