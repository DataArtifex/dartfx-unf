# SPDX-FileCopyrightText: 2024-present kulnor <pascal@codata.org>
#
# SPDX-License-Identifier: MIT

"""Serializers for UNF reports (JSON, human-friendly tables)."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from dartfx.unf.__about__ import __version__

if TYPE_CHECKING:
    from dartfx.unf.report import UNFReport


class JSONSerializer:
    """Serializer for UNF reports to JSON format.

    This class encapsulates the logic for converting a ``UNFReport`` object
    into a JSON-compatible dictionary and then into a JSON string.
    It supports validation against the project's JSON schema.
    """

    def __init__(
        self,
        indent: int = 2,
        validate: bool = False,
    ) -> None:
        self.indent = indent
        self.validate = validate

    def to_dict(self, report: UNFReport) -> dict[str, Any]:
        """Convert a report to a dictionary matching the UNF JSON schema."""
        metadata: dict[str, Any] = {
            "timestamp": report.timestamp,
            "parameters": {
                "N": report.params.digits,
                "X": report.params.characters,
                "H": report.params.hash_bits,
                "rounding_mode": (
                    "R1_truncate" if report.params.truncate else "IEEE_754_nearest_even"
                ),
            },
            "options": _prune_empty(report.options),
            "software": {
                "name": "dartfx-unf",
                "version": __version__,
            },
        }

        # Build result dict, removing empty optional fields.
        result_dict = asdict(report.result)
        result_dict = _prune_empty(result_dict)

        data = {
            "unf_version": report.unf_version,
            "metadata": metadata,
            "result": result_dict,
        }

        if self.validate:
            self._validate_dict(data)

        return data

    def _validate_dict(self, data: dict[str, Any]) -> None:
        """Validate the dictionary against the bundled JSON schema."""
        from importlib.resources import files

        # Deferred import to avoid hard dependency on jsonschema for simple usage
        from jsonschema import validate as validate_json

        # Find bundled schema
        schema_resource = files("dartfx.unf").joinpath("unf.schema.json")
        with schema_resource.open(encoding="utf-8") as f:
            schema = json.load(f)
        validate_json(instance=data, schema=schema)

    def serialize(self, report: UNFReport) -> str:
        """Serialize the report to a JSON string."""
        return json.dumps(self.to_dict(report), indent=self.indent)


class TableSerializer:
    """Serializer for UNF reports to human-friendly summary tables."""

    def serialize(self, report: UNFReport) -> str:
        """Serialize the report to a formatted summary table string."""
        from dartfx.unf.report import DatasetResult, FileResult

        res = report.result
        lines = []
        lines.append("-" * 80)
        lines.append(f"UNF Report: {res.label}")
        lines.append(f"Version:    {report.unf_version}")
        lines.append(f"UNF:        {res.unf}")
        lines.append(
            f"Parameters: N={report.params.digits}, X={report.params.characters}, "
            f"H={report.params.hash_bits}, R1={1 if report.params.truncate else 0}"
        )
        lines.append("-" * 80)

        if isinstance(res, FileResult):
            lines.append(f"{'COLUMN':<30} | {'TYPE':<12} | {'UNF'}")
            lines.append("-" * 80)
            for col in res.columns:
                lines.append(f"{col.name[:30]:<30} | {col.type:<12} | {col.unf}")
        elif isinstance(res, DatasetResult):
            lines.append(f"{'FILE':<30} | {'UNF'}")
            lines.append("-" * 80)
            for entry in res.entries:
                lines.append(f"{entry.label[:30]:<30} | {entry.unf}")

        lines.append("-" * 80)
        return "\n".join(lines)


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
        elif v != "" or isinstance(v, bool):
            pruned[k] = v
    return pruned
