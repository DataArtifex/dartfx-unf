# SPDX-FileCopyrightText: 2024-present kulnor <pascal@codata.org>
#
# SPDX-License-Identifier: MIT

"""Structured report model for UNF results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from dartfx.unf.parameters import UNFParameters


@dataclass
class ColumnResult:
    """UNF result for a single column (vector)."""

    name: str
    type: str = ""
    unf: str = ""


@dataclass
class FileResult:
    """UNF result for a single file (data frame)."""

    type: str = "file"
    label: str = ""
    unf: str = ""
    columns: list[ColumnResult] = field(default_factory=list)


@dataclass
class DatasetResult:
    """UNF result for a dataset (multiple files)."""

    type: str = "dataset"
    label: str = ""
    unf: str = ""
    entries: list[FileResult] = field(default_factory=list)


@dataclass
class UNFReport:
    """A structured report containing the final results of a UNF calculation.

    This class wraps the final fingerprint (which can be a file-level result or a
    dataset-level result), the parameters used for the calculation, and a
    timestamp. It provides built-in methods for serializing the results to
    standard JSON formats that comply with the project's JSON schema.

    Examples
    --------
    >>> from dartfx.unf import unf_file
    >>> report = unf_file("data.parquet")
    >>> # Save as a validated JSON file
    >>> with open("report.json", "w") as f:
    ...     f.write(report.to_json(validate=True))

    >>> # Get just the top-level UNF
    >>> print(report.result.unf)
    UNF:6:Do5dfAoOOFt4FSj0JcByEw==
    """

    result: FileResult | DatasetResult
    params: UNFParameters = field(default_factory=UNFParameters)
    timestamp: str = ""
    unf_version: str = "6"
    options: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()

    def to_dict(self, *, validate: bool = False) -> dict[str, Any]:
        """Serialize the report to a plain dict matching the JSON schema.

        If *validate* is True, the resulting dict is validated against
        the bundled ``unf.schema.json`` using the ``jsonschema`` library.
        """
        from dartfx.unf.serializers import JSONSerializer

        serializer = JSONSerializer(validate=validate)
        return serializer.to_dict(self)

    def to_json(self, indent: int = 2, *, validate: bool = False) -> str:
        """Serialize the report to a JSON string."""
        from dartfx.unf.serializers import JSONSerializer

        serializer = JSONSerializer(indent=indent, validate=validate)
        return serializer.serialize(self)


def _prune_empty(d: dict[str, Any]) -> dict[str, Any]:
    """Recursively remove keys with empty string values."""
    from dartfx.unf.serializers import _prune_empty as _prune

    return _prune(d)
