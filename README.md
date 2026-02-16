# dartfx-unf

[![PyPI - Version](https://img.shields.io/pypi/v/dartfx-unf.svg)](https://pypi.org/project/dartfx-unf)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/dartfx-unf.svg)](https://pypi.org/project/dartfx-unf)
[![CI](https://github.com/DataArtifex/dartfx-unf/actions/workflows/test.yml/badge.svg)](https://github.com/DataArtifex/dartfx-unf/actions/workflows/test.yml)
[![License](https://img.shields.io/github/license/DataArtifex/dartfx-unf.svg)](https://github.com/DataArtifex/dartfx-unf/blob/main/LICENSE.txt)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Documentation](https://img.shields.io/badge/docs-v6-blue)](https://dataartifex.github.io/dartfx-unf/)

**A high-performance Python implementation of the Universal Number Fingerprint (UNF) v6 specification.**

## Overview

`dartfx-unf` is a blazing-fast, memory-efficient calculator for [UNF Version 6](https://guides.dataverse.org/en/latest/developers/unf/unf-v6.html). Developed by DataArtifex, it ensures that your data remains identifiable and consistent across different software versions, file formats, and operating systems by normalizing and hashing the underlying data values rather than the file itself.

Built on top of the **Polars** engine, it provides native support for massive datasets with a professional-grade CLI and a clean Python API.

*This package was vibe coded with Claude Opus 4.6 and Gemini 3 Flash.*

---

## Key Features

- ✅ **Full Compliance**: Implements the complete UNF v6 spec (Numeric, String, Date/Time, Bit Fields, and Booleans).
- 🚀 **Polars-Powered Speed**: Near-C performance using vectorized Rust-based execution.
- 🧊 **Out-of-Core Streaming**: Process multi-gigabyte files with constant memory overhead.
- 📦 **Multi-Format**: Native support for Parquet and CSV.
- 📋 **Structured Reporting**: Generates detailed JSON reports compliant with a built-in schema.
- 🔗 **Dataset Hashing**: Combine fingerprints from multiple files into a single dataset-level hash.

---

## Installation

We recommend using [uv](https://github.com/astral-sh/uv) for fast environment management.

### For Users
```bash
pip install dartfx-unf
```

### For Developers
```bash
git clone https://github.com/DataArtifex/dartfx-unf.git
cd dartfx-unf
uv sync
```

---

## Quick Start

### Command Line Interface

Calculate fingerprints directly from your terminal:

```bash
# Basic JSON report
uv run dartfx-unf data.parquet

# Quiet mode (just the hash)
uv run dartfx-unf --quiet data.parquet

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

For more details, see our [Full Documentation](https://dataartifex.github.io/dartfx-unf/).

---

## Why Polars?

To meet the high-performance and "streaming" requirements of modern data science, `dartfx-unf` leverages Polars:

- **Vectorized Expressions**: Normalization steps map directly to efficient SIMD operations.
- **Lazy Execution**: Optimizes I/O and computation order.
- **Memory Efficiency**: Polars' streaming mode allows us to hash files that are larger than the available RAM.

---

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines and the [Implementation Roadmap](IMPLEMENTATION.md) for current progress.

## License

This project is licensed under the MIT License. See [LICENSE.txt](LICENSE.txt) for details.
