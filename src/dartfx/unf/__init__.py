# SPDX-FileCopyrightText: 2024-present kulnor <pascal@codata.org>
#
# SPDX-License-Identifier: MIT

"""
`dartfx-unf` is a high-performance Python implementation of the Universal Number
Fingerprint (UNF) v6 specification, built on the Polars engine.

The library provides tools to calculate system-independent digital signatures
(fingerprints) for data objects, ensuring data integrity across different
environments and formats.

Key Features
------------
* **Column-level hashing**: Fingerprint individual Polars Series.
* **File-level hashing**: Supports CSV, Parquet, and TSV with automatic format
  detection.
* **Dataset-level hashing**: Combine fingerprints from multiple files into a single
  hash.
* **Out-of-core processing**: Efficiently handle massive datasets using streaming.

Public API
----------
- :func:`~dartfx.unf.core.unf_column`: Calculate UNF for a single vector.
- :func:`~dartfx.unf.core.unf_file`: Calculate UNF for a data file.
- :func:`~dartfx.unf.core.unf_dataset`: Combine fingerprints from multiple files.
- :class:`~dartfx.unf.parameters.UNFParameters`: Configuration for the algorithm.
- :class:`~dartfx.unf.report.UNFReport`: Structured results and metadata.

Quick Example
-------------
>>> from dartfx.unf import unf_file
>>> report = unf_file("data.parquet")
>>> print(report.result.unf)
"""

from dartfx.unf.__about__ import __version__
from dartfx.unf.core import unf_column, unf_dataset, unf_file
from dartfx.unf.parameters import UNFParameters
from dartfx.unf.report import UNFReport
from dartfx.unf.schema import (
    json_schema_to_polars_schema,
    parse_schema_file,
    parse_schema_inline,
    parse_schema_input,
)
from dartfx.unf.serializers import JSONSerializer, TableSerializer

__all__ = [
    "__version__",
    "JSONSerializer",
    "TableSerializer",
    "UNFParameters",
    "UNFReport",
    "json_schema_to_polars_schema",
    "parse_schema_file",
    "parse_schema_inline",
    "parse_schema_input",
    "unf_column",
    "unf_dataset",
    "unf_file",
]
