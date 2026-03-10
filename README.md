# dartfx-unf

[![Documentation](https://img.shields.io/badge/docs-blue)](https://www.dataartifex.org/docs/dartfx-unf/)
[![DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/DataArtifex/dartfx-unf)
[![Package Status](https://img.shields.io/badge/PyPI-not%20published-lightgrey)](https://github.com/DataArtifex/dartfx-unf)
[![CI](https://github.com/DataArtifex/dartfx-unf/actions/workflows/test.yml/badge.svg)](https://github.com/DataArtifex/dartfx-unf/actions/workflows/test.yml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![License](https://img.shields.io/github/license/DataArtifex/dartfx-unf.svg)](https://github.com/DataArtifex/dartfx-unf/blob/main/LICENSE.txt)

**A high-performance Python implementation of the [Universal Numerical Fingerprint (UNF) v6 specification]((https://guides.dataverse.org/en/latest/developers/unf/unf-v6.html)), a format agnostic standard for data fingerprinting.**

> [!WARNING]
> **Prototype Status**: Full alignment with the UNF v6 specification and the canonical Java Dataverse implementation is still a **work in progress**. This package should be treated as a prototype for evaluation purposes only and is **not for production use** at this time.

## Overview

`dartfx-unf` is a blazing-fast, memory-efficient calculator for [UNF Version 6](https://guides.dataverse.org/en/latest/developers/unf/unf-v6.html). It ensures that your data remains identifiable and consistent across different software versions, file formats, and operating systems by normalizing and hashing the underlying data values rather than the file itself.

Built on top of the **Polars** engine, it provides native support for massive datasets with a professional-grade CLI and a clean Python API.

*This package was vibe coded with Claude Opus 4.6 and Gemini 3 Flash.*

---

### 🛡️ Compliance & Interoperability

The primary goal of `dartfx-unf` is two-fold:
1.  **Specification Compliance**: strictly follow the [UNF v6 specification](https://guides.dataverse.org/en/latest/developers/unf/unf-v6.html).
2.  **Canonical Alignment**: ensure full interoperability with the [canonical Java Dataverse implementation](https://github.com/IQSS/UNF).

The Java implementation has produced thousands of persistent fingerprints over the years that cannot be changed. Interoperability is just as critical as compliance.

**Handling Ambiguity**: In cases where the specification can be interpreted in multiple ways, `dartfx-unf` provides configuration options to ensure flexibility. While different options can naturally result in different UNFs, the resulting **JSON reports document every option used** for absolute traceability.

## Key Features

- ✅ **Out-of-Core Streaming**: Process multi-gigabyte files with constant memory overhead.
- ✅ **Canonical Alignment (WIP)**: Aims for parity with the Java Dataverse codebase.
- 📦 **Multi-Format**: Native support for Parquet, CSV, and statistical formats (SAS, Stata, SPSS).
- 📋 **Structured Reporting**: Generates detailed JSON reports documenting all options for full traceability.
- 🔗 **Dataset Hashing**: Combine fingerprints from multiple files into a single dataset-level hash.


## Installation

We recommend using [uv](https://github.com/astral-sh/uv) for fast environment management.

This package is not yet published on PyPI. Install from source using the steps below.

### For Users
```bash
git clone https://github.com/DataArtifex/dartfx-unf.git
cd dartfx-unf

# Option 1: pip (editable install)
pip install -e .

# Option 2: uv (editable install)
uv pip install -e .
```

### For Developers
```bash
git clone https://github.com/DataArtifex/dartfx-unf.git
cd dartfx-unf
uv sync
```

## Quick Start

### Command Line Interface

Calculate fingerprints directly from your terminal:

```bash
# Basic JSON report
uv run dartfx-unf data.parquet

# Disable automatic date parsing for CSVs
uv run dartfx-unf --no-parse-date data.csv

# Quiet mode (just the hash)
uv run dartfx-unf --quiet data.parquet

# Match Dataverse's exact behavior for CSVs (treats empty fields as empty strings)
uv run dartfx-unf --null-as-strings --scan-length -1 data.csv


# Detailed summary table
uv run dartfx-unf --verbose file1.csv file2.parquet
```

### Python API

Integrate UNF calculation into your data pipelines:

```python
from dartfx.unf import unf_file

# Calculate and print the hash
report = unf_file("results.parquet")
print(f"UNF: {report.result.unf}")

# Export to validated JSON
json_report = report.to_json(validate=True)
```

> 📚 **Documentation**: Complete documentation is accessible at [http://dataartifex.org/docs/dartfx-unf](https://dataartifex.org/docs/dartfx-unf)


## Why Polars?

To meet the high-performance and "streaming" requirements of modern data science, `dartfx-unf` leverages Polars:

- **Vectorized Expressions**: Normalization steps map directly to efficient SIMD operations.
- **Lazy Execution**: Optimizes I/O and computation order.
- **Memory Efficiency**: Polars' streaming mode allows us to hash files that are larger than the available RAM.


## UNF in Practice

The UNF algorithm is **format-agnostic** and **column-order invariant**. It ensures that identical dataset values produce the same fingerprint regardless of how they are stored.

### Example: Basic Atomic Values

UNF can be used to calculate a fingerprint for a single value (a "vector" of one element). Identical values across different types (e.g., Integer vs Float) or representations (e.g., Date vs String) results in consistent hashes when normalized according to the specification.

| Data Type | Value | Normalized Form (§Ia) | Resulting UNF |
|---|---|---|---|
| **Numeric** | `1` / `1.0` | `+1.e+` | `UNF:6:tv3XYCv524AfmlFyVOhuZg==` |
| **Numeric** | `0` / `-0.0` | `+0.e+` / `-0.e+` | *See spec for sign details* |
| **String** | `"A character String"` | `"A character String\n\0"` | `UNF:6:FYqU7uBl885eHMbpco1ooA==` |
| **Date** | `2014-01-13` | `"2014-01-13\n\0"` | `UNF:6:PH+jFA4u+yJSs1sIw64dyw==` |
| **Boolean** | `true` | `+1.e+` | `UNF:6:tv3XYCv524AfmlFyVOhuZg==` |


### Example: Data & Format Invariance

The UNF remains identical even if we swap the column order or change the storage format (e.g., from CSV to Parquet).

**dataset_v1.csv**:
```csv
id,name,sex,dob,income
1,Alice,F,2007-01-12,75000
2,Bob,M,1985-05-15,160000
3,Charlie,M,1992-08-20,50000
```

**dataset_v2.csv** (Columns reordered):
```csv
id,income,dob,name,sex
1,75000,2007-01-12,Alice,F
2,160000,1985-05-15,Bob,M
3,50000,1992-08-20,Charlie,M
```

All variations yield the same fingerprint:
```bash
# Original CSV
$ uv run dartfx-unf --quiet dataset_v1.csv
UNF:6:/iH9nCE4fZqn1rBrrsOc7w==

# CSV with different column order
$ uv run dartfx-unf --quiet dataset_v2.csv
UNF:6:/iH9nCE4fZqn1rBrrsOc7w==

# Binary Parquet version of the same data
$ uv run dartfx-unf --quiet dataset_v1.parquet
UNF:6:/iH9nCE4fZqn1rBrrsOc7w==
```

> 💡 **Note**: If you change the **row order**, the UNF *will* change, as the sequence of observations is significant.

### Example: Variable (Column) UNFs

You can inspect the fingerprints of individual variables. This is useful for identifying which specific column changed between two versions of a dataset.

```bash
$ uv run dartfx-unf --verbose dataset_v1.csv
```

**Output:**
```text
COLUMN                         | TYPE         | UNF
--------------------------------------------------------------------------------
id                             | numeric      | UNF:6:AvELPR5QTaBbnq6S22Msow==
name                           | string       | UNF:6:G3RHxSQPXELRGHIJ+FV6qA==
sex                            | string       | UNF:6:VSDSXcRD7ShBmQqv1WR9EA==
dob                            | date         | UNF:6:PH+jFA4u+yJSs1sIw64dyw==
income                         | numeric      | UNF:6:v/5E9kHI79TVvlGYinvxTQ==
```

### Example: Choosing Precision

You can customize the normalization parameters (digits of precision, hash bits, etc.). Changes to these parameters are automatically encoded in the resulting UNF header:

```bash
# Standard 7-digit precision (Default)
$ uv run dartfx-unf --quiet dataset_v1.csv
UNF:6:/iH9nCE4fZqn1rBrrsOc7w==

# Higher 9-digit precision
$ uv run dartfx-unf --quiet --digits 9 dataset_v1.csv
UNF:6:N9:NvK8CwEepCVQZdjiFCGf2A==
```


## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines and the [Implementation Roadmap](IMPLEMENTATION.md) for current progress.

## License

This project is licensed under the MIT License. See [LICENSE.txt](LICENSE.txt) for details.
