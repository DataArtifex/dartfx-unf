dartfx-unf: High-Performance UNF v6
=====================================

.. image:: https://img.shields.io/pypi/v/dartfx-unf.svg
   :target: https://pypi.org/project/dartfx-unf
   :alt: PyPI Version

.. image:: https://img.shields.io/github/license/DataArtifex/dartfx-unf.svg
   :target: https://github.com/DataArtifex/dartfx-unf/blob/main/LICENSE.txt
   :alt: License

**dartfx-unf** is a blazing-fast, memory-efficient Python implementation of the **Universal Number Fingerprint (UNF) v6** specification. Built on the **Polars** engine, it is designed to handle massive datasets with "out-of-core" streaming capabilities.

.. warning::
   **Prototype Status**: Full alignment on the UNF v6 specification and the canonical Java Dataverse implementation is a **work in progress**. This package should be treated as a **prototype for evaluation purposes only** and is **not intended for production use** at this time.

Compliance & Interoperability
------------------------------

This package aims to both strictly comply with the **UNF v6 specification** and remain fully aligned with the **canonical Java Dataverse implementation** (from `IQSS/UNF <https://github.com/IQSS/UNF>`_).

Because the Java implementation has produced thousands of persistent fingerprints over many years, maintaining interoperability is a primary design goal. Where the specification is subject to interpretation, **dartfx-unf** provides configuration options for flexibility. All options used for a given run are explicitly documented in the resulting JSON metadata for full auditability and traceability.

Key Features
------------

*  **Canonical Alignment (WIP)**: Aims for parity with the Java Dataverse codebase.
*  **High Performance**: Leverages the Rust-powered Polars engine for columnar operations.
*  **Streaming Support**: Process datasets larger than RAM with minimal memory footprint.
*  **Multi-Format**: Native support for Parquet, CSV, and statistical formats (SAS, Stata, SPSS).

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
