dartfx-unf: High-Performance UNF v6
=====================================

.. image:: https://img.shields.io/pypi/v/dartfx-unf.svg
   :target: https://pypi.org/project/dartfx-unf
   :alt: PyPI Version

.. image:: https://img.shields.io/github/license/DataArtifex/dartfx-unf.svg
   :target: https://github.com/DataArtifex/dartfx-unf/blob/main/LICENSE.txt
   :alt: License

**dartfx-unf** is a blazing-fast, memory-efficient Python implementation of the **Universal Number Fingerprint (UNF) v6** specification. Built on the **Polars** engine, it is designed to handle massive datasets with "out-of-core" streaming capabilities.

Key Features
------------

*  **Full Compliance**: Implements the complete UNF v6 specification, including numeric, string, date/time, and bit field normalization.
*  **High Performance**: Leverages the Rust-powered Polars engine for columnar operations.
*  **Streaming Support**: Process datasets larger than RAM with minimal memory footprint.
*  **Multi-Format**: Native support for Parquet and CSV.

.. toctree::
   :maxdepth: 2
   :caption: Getting Started:

   usage
   schema
   spec_summary

.. toctree::
   :maxdepth: 2
   :caption: API Reference:

   api/modules

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
