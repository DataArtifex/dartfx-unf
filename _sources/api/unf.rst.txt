API Reference
=============

This section provides a detailed reference for all the modules, classes, and functions available in `dartfx-unf`.

Top-Level Interface
-------------------

For most common tasks, you can use the functions re-exported at the package level.

.. automodule:: dartfx.unf
   :noindex:

Core Computation
----------------

The `dartfx.unf.core` module contains the main logic for file, dataset, and vector-level hashing.

.. automodule:: dartfx.unf.core
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: UNFParameters, UNFReport, finalize_hash, combine_unfs, should_stream, normalize_bit_field, normalize_boolean, normalize_date, normalize_datetime, normalize_duration, normalize_missing, normalize_numeric, normalize_string, normalize_time, MISSING_VALUE, VALUE_TERMINATOR

Configuration & Parameters
--------------------------

Use `UNFParameters` to control the precision and behavior of the fingerprinting algorithm.

.. automodule:: dartfx.unf.parameters
   :members:
   :undoc-members:
   :show-inheritance:

Reporting & Results
-------------------

The `dartfx.unf.report` module provides the structured models used to represent the output of a UNF calculation.

.. automodule:: dartfx.unf.report
   :members:
   :undoc-members:
   :show-inheritance:

Normalization Logic
-------------------

Internal functions responsible for spec-compliant data normalization.

.. automodule:: dartfx.unf.normalize
   :members:
   :undoc-members:
   :show-inheritance:

Internal Utilities
------------------

.. automodule:: dartfx.unf.hasher
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: dartfx.unf.memory
   :members:
   :undoc-members:
   :show-inheritance:
