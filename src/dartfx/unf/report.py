# SPDX-FileCopyrightText: 2024-present kulnor <pascal@codata.org>
#
# SPDX-License-Identifier: MIT

"""Structured report model for UNF results."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from dartfx.unf.__about__ import __version__
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

    Attributes
    ----------
    result : FileResult | DatasetResult
        The core result of the calculation. A ``FileResult`` contains column-level
        UNFs, while a ``DatasetResult`` contains file-level results.
    params : UNFParameters
        The configuration used (digits, hash_bits, etc.).
    timestamp : str, optional
        ISO 8601 timestamp of when the report was generated. Set automatically
        during initialization if not provided.
    unf_version : str, default "6"
        The version of the UNF specification used.

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

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()

    def to_dict(self, *, validate: bool = False) -> dict[str, Any]:
        """Serialise the report to a plain dict matching the JSON schema.

        If *validate* is True, the resulting dict is validated against
        the bundled ``unf6_schema.json`` using the ``jsonschema`` library.
        """
        metadata: dict[str, Any] = {
            "timestamp": self.timestamp,
            "parameters": {
                "N": self.params.digits,
                "X": self.params.characters,
                "H": self.params.hash_bits,
                "rounding_mode": (
                    "R1_truncate" if self.params.truncate else "IEEE_754_nearest_even"
                ),
            },
            "software": {
                "name": "dartfx-unf",
                "version": __version__,
            },
        }

        # Build result dict, removing empty optional fields.
        result_dict = asdict(self.result)
        result_dict = _prune_empty(result_dict)

        report = {
            "unf_version": "6",
            "metadata": metadata,
            "result": result_dict,
        }

        if validate:
            from importlib.resources import files

            from jsonschema import validate as validate_json

            # Find bundled schema
            schema_resource = files("dartfx.unf").joinpath("unf6_schema.json")
            with schema_resource.open(encoding="utf-8") as f:
                schema = json.load(f)
            validate_json(instance=report, schema=schema)

        return report

    def to_json(self, indent: int = 2, *, validate: bool = False) -> str:
        """Serialise the report to a JSON string."""
        return json.dumps(self.to_dict(validate=validate), indent=indent)


def _prune_empty(d: dict[str, Any]) -> dict[str, Any]:
    """Recursively remove keys with empty string values."""
    pruned: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, dict):
            pruned[k] = _prune_empty(v)
        elif isinstance(v, list):
            pruned[k] = [
                _prune_empty(item) if isinstance(item, dict) else item for item in v
            ]
        elif v != "":
            pruned[k] = v
    return pruned
