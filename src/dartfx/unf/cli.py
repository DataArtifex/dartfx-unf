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

    # --- null handling ---
    null_group = parser.add_mutually_exclusive_group()
    null_group.add_argument(
        "--null-as-string",
        dest="null_handling",
        action="store_const",
        const="null-as-string",
        help=(
            "Treat columns with null values as strings and normalize those "
            "nulls as empty strings for bit-for-bit Dataverse parity."
        ),
    )
    null_group.add_argument(
        "--null-as-null",
        dest="null_handling",
        action="store_const",
        const="null-as-null",
        help="Treat nulls as nulls without inferring string (default).",
    )
    parser.set_defaults(null_handling="null-as-null")
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
            null_handling=args.null_handling,
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
            null_handling=args.null_handling,
        )

    if args.verbose:
        from dartfx.unf.serializers import TableSerializer

        print(TableSerializer().serialize(report))
    elif args.quiet:
        print(report.result.unf)
    elif args.output:
        output_path = Path(args.output)
        output_path.write_text(report.to_json(validate=args.validate), encoding="utf-8")
        print(f"Report written to {output_path}")
    else:
        print(report.to_json(validate=args.validate))

    return 0


if __name__ == "__main__":
    sys.exit(main())
