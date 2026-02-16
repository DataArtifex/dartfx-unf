# SPDX-FileCopyrightText: 2024-present kulnor <pascal@codata.org>
#
# SPDX-License-Identifier: MIT

"""Benchmark for UNF v6 performance."""

import time
from datetime import date, timedelta
from pathlib import Path

import polars as pl

from dartfx.unf.core import unf_file


def create_benchmark_data(n_rows: int = 100_000) -> Path:
    """Create a temporary CSV file with mixed data types."""
    path = Path(f"benchmarks/data_{n_rows}_benchmark.parquet")
    if path.exists():
        return path

    df = pl.DataFrame(
        {
            "id": range(n_rows),
            "val_int": [i % 1000 for i in range(n_rows)],
            "val_float": [i * 1.23456789 for i in range(n_rows)],
            "val_str": [f"label_{i % 100}" for i in range(n_rows)],
            "val_bool": [i % 2 == 0 for i in range(n_rows)],
            "val_date": pl.date_range(
                start=date(2000, 1, 1),
                end=date(2000, 1, 1) + timedelta(days=n_rows - 1),
                interval="1d",
                eager=True,
            ),
        }
    )
    df.write_parquet(path)
    return path


def run_benchmark():
    n_rows = 100_000
    path = create_benchmark_data(n_rows)
    print(f"Benchmarking with {n_rows:,} rows...")

    # In-memory benchmark
    start = time.perf_counter()
    report = unf_file(path, streaming=False)
    end = time.perf_counter()
    print(f"In-memory: {end - start:.4f} seconds (UNF: {report.result.unf})")

    # Streaming benchmark
    start = time.perf_counter()
    report = unf_file(path, streaming=True, batch_size=20_000)
    end = time.perf_counter()
    print(f"Streaming: {end - start:.4f} seconds (UNF: {report.result.unf})")

    # path.unlink()


if __name__ == "__main__":
    run_benchmark()
