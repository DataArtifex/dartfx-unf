# SPDX-FileCopyrightText: 2024-present kulnor <pascal@codata.org>
#
# SPDX-License-Identifier: MIT

"""Command-line interface for dartfx-unf."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dartfx.unf.__about__ import __version__
from dartfx.unf.core import unf_dataset, unf_file
from dartfx.unf.parameters import UNFParameters
from dartfx.unf.report import UNFReport


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dartfx-unf",
        description="Calculate UNF v6 fingerprints for CSV and Parquet data files.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "files",
        nargs="+",
        help=(
            "One or more data files (.csv, .tsv, .parquet, .sav, .zsav, "
            ".dta, .sas7bdat, .xpt)."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Write JSON report to this file instead of stdout.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Print only the top-level UNF to stdout (no JSON).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print a human-friendly summary table (ignores --quiet).",
    )
    parser.add_argument(
        "--digits",
        type=int,
        default=7,
        metavar="N",
        help="Significant digits for numeric precision (default: 7).",
    )
    parser.add_argument(
        "--characters",
        type=int,
        default=128,
        metavar="X",
        help="String truncation length (default: 128).",
    )
    parser.add_argument(
        "--hash-bits",
        type=int,
        default=128,
        metavar="H",
        choices=[128, 192, 196, 256],
        help="SHA-256 hash truncation in bits (default: 128).",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Use truncation instead of rounding (R1 mode).",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate JSON report against schema.",
    )
    parser.add_argument(
        "--label",
        type=str,
        default=None,
        help="Optional label for the dataset or file.",
    )

    # --- streaming / performance ---
    streaming_group = parser.add_mutually_exclusive_group()
    streaming_group.add_argument(
        "--streaming",
        action="store_true",
        default=None,
        help="Force streaming mode (constant memory, batched I/O).",
    )
    streaming_group.add_argument(
        "--no-streaming",
        dest="streaming",
        action="store_false",
        help="Force in-memory mode (faster for small files).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100_000,
        metavar="ROWS",
        help="Rows per batch in streaming mode (default: 100000).",
    )
    parser.add_argument(
        "--scan-length",
        type=int,
        default=10_000,
        metavar="ROWS",
        help="Rows to scan for CSV schema inference (default: 10000, use -1 for all).",
    )
    parser.add_argument(
        "--schema",
        type=str,
        default=None,
        metavar="SCHEMA",
        help="JSON Schema file or inline JSON for type overrides.",
    )

    # --- date parsing ---
    date_group = parser.add_mutually_exclusive_group()
    date_group.add_argument(
        "--parse-date",
        dest="parse_date",
        action="store_true",
        default=False,
        help="Attempt to auto-parse dates in CSV files (default: False).",
    )
    date_group.add_argument(
        "--no-parse-date",
        dest="parse_date",
        action="store_false",
        help="Disable automatic date parsing.",
    )

    # --- leading zeros ---
    lz_group = parser.add_mutually_exclusive_group()
    lz_group.add_argument(
        "--leading-zeros",
        dest="leading_zeros",
        action="store_true",
        default=False,
        help="Auto-detect and preserve leading zeros in CSVs (default: False).",
    )
    lz_group.add_argument(
        "--no-leading-zeros",
        dest="leading_zeros",
        action="store_false",
        help="Disable automatic leading zero detection.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Parameters
    ----------
    argv : list of str, optional
        Command-line arguments.  Uses ``sys.argv`` if not provided,
        making this function easy to call from tests or other code.

    Returns
    -------
    int
        Exit code (0 for success).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    params = UNFParameters(
        digits=args.digits,
        characters=args.characters,
        hash_bits=args.hash_bits,
        truncate=args.truncate,
    )

    # Validate that all files exist before processing
    paths = [Path(f) for f in args.files]
    for p in paths:
        if not p.exists():
            print(f"Error: file not found: {p}", file=sys.stderr)
            return 1

    # Single file → file-level report; multiple files → dataset-level
    if len(paths) == 1:
        report = unf_file(
            paths[0],
            params=params,
            label=args.label,
            streaming=args.streaming,
            batch_size=args.batch_size,
            infer_schema_length=args.scan_length,
            schema=args.schema,
            parse_dates=args.parse_date,
            detect_leading_zeros=args.leading_zeros,
        )
    else:
        report = unf_dataset(
            paths,
            params=params,
            label=args.label,
            streaming=args.streaming,
            batch_size=args.batch_size,
            infer_schema_length=args.scan_length,
            schema=args.schema,
            parse_dates=args.parse_date,
            detect_leading_zeros=args.leading_zeros,
        )

    if args.verbose:
        _print_verbose(report)
    elif args.quiet:
        print(report.result.unf)
    elif args.output:
        output_path = Path(args.output)
        output_path.write_text(report.to_json(validate=args.validate), encoding="utf-8")
        print(f"Report written to {output_path}")
    else:
        print(report.to_json(validate=args.validate))

    return 0


def _print_verbose(report: UNFReport) -> None:
    """Print a human-friendly summary table of the UNF report."""
    from dartfx.unf.report import DatasetResult, FileResult

    res = report.result
    print("-" * 80)
    print(f"UNF Report: {res.label}")
    print(f"Version:    {report.unf_version}")
    print(f"UNF:        {res.unf}")
    print(
        f"Parameters: N={report.params.digits}, X={report.params.characters}, "
        f"H={report.params.hash_bits}, R1={1 if report.params.truncate else 0}"
    )
    print("-" * 80)

    if isinstance(res, FileResult):
        print(f"{'COLUMN':<30} | {'TYPE':<12} | {'UNF'}")
        print("-" * 80)
        for col in res.columns:
            print(f"{col.name[:30]:<30} | {col.type:<12} | {col.unf}")
    elif isinstance(res, DatasetResult):
        print(f"{'FILE':<30} | {'UNF'}")
        print("-" * 80)
        for entry in res.entries:
            print(f"{entry.label[:30]:<30} | {entry.unf}")

    print("-" * 80)


if __name__ == "__main__":
    sys.exit(main())
