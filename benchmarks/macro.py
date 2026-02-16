# SPDX-FileCopyrightText: 2024-present kulnor <pascal@codata.org>
#
# SPDX-License-Identifier: MIT

"""Macro-benchmarking suite for dartfx-unf."""

import argparse
import gc
import json
import time
from datetime import date, timedelta
from pathlib import Path
from threading import Event, Thread

import polars as pl
import psutil

from dartfx.unf.core import unf_file


def get_memory_usage():
    """Return current RSS memory in MiB."""
    process = psutil.Process()
    # RSS (Resident Set Size) is the non-swapped physical memory a process has used.
    return process.memory_info().rss / (1024 * 1024)


class PeakMemoryTracker(Thread):
    """Thread-based peak RSS memory tracker."""

    def __init__(self, interval=0.1):
        super().__init__(daemon=True)
        self.interval = interval
        self.peak_memory = 0.0
        self.stop_event = Event()

    def run(self):
        while not self.stop_event.is_set():
            current = get_memory_usage()
            if current > self.peak_memory:
                self.peak_memory = current
            time.sleep(self.interval)

    def stop(self):
        self.stop_event.set()


def create_synthetic_data(n_rows: int, format: str = "parquet") -> Path:
    """Generate a synthetic dataset with mixed types."""
    path = Path(f"benchmarks/data_{n_rows}_{format}.{format}")
    if path.exists():
        print(f"  (Using existing {path})")
        return path

    print(f"  Generating {n_rows:,} rows of synthetic data...")

    # Simple generation for benchmark
    df = pl.DataFrame(
        {
            "id": pl.Series(range(n_rows), dtype=pl.Int64),
            "val_int": pl.Series([i % 1000 for i in range(n_rows)], dtype=pl.Int32),
            "val_float": pl.Series(
                [i * 1.23456789 for i in range(n_rows)], dtype=pl.Float64
            ),
            "val_str": pl.Series(
                [f"label_{i % 100}" for i in range(n_rows)], dtype=pl.Utf8
            ),
            "val_bool": pl.Series(
                [i % 2 == 0 for i in range(n_rows)], dtype=pl.Boolean
            ),
            "val_date": pl.date_range(
                start=date(2000, 1, 1),
                end=date(2000, 1, 1) + timedelta(days=n_rows - 1),
                interval="1d",
                eager=True,
            ),
        }
    )

    if format == "parquet":
        df.write_parquet(path)
    else:
        df.write_csv(path)

    return path


def run_test(path: Path, n_rows: int, streaming: bool, batch_size: int):
    """Run a single UNF calculation and return performance metrics."""
    gc.collect()
    time.sleep(1)  # Settling

    tracker = PeakMemoryTracker()
    tracker.start()

    start_time = time.perf_counter()
    report = unf_file(path, streaming=streaming, batch_size=batch_size)
    duration = time.perf_counter() - start_time

    tracker.stop()
    tracker.join()

    rows_per_sec = n_rows / duration if duration > 0 else 0

    return {
        "mode": "Streaming" if streaming else "In-Memory",
        "rows": n_rows,
        "duration": duration,
        "rows_per_sec": rows_per_sec,
        "peak_memory_mib": tracker.peak_memory,
        "unf": report.result.unf,
        "file_size_mib": path.stat().st_size / (1024 * 1024),
    }


def main():
    parser = argparse.ArgumentParser(description="UNF Macro Benchmark")
    parser.add_argument(
        "--rows",
        type=int,
        nargs="+",
        default=[100_000, 1_000_000],
        help="Row counts to test",
    )
    parser.add_argument(
        "--format", choices=["csv", "parquet"], default="parquet", help="File format"
    )
    parser.add_argument(
        "--batch-size", type=int, default=100_000, help="Batch size for streaming"
    )
    parser.add_argument("--output", type=str, help="Save results to JSON file")
    args = parser.parse_args()

    results = []
    print("=" * 60)
    print(
        f"{'ROWS':<12} | {'MODE':<10} | {'TIME (s)':<10} | "
        f"{'ROWS/s':<10} | {'PEAK RAM'}"
    )
    print("-" * 60)

    for n in args.rows:
        path = create_synthetic_data(n, args.format)

        # Test 1: In-Memory (if possible)
        # Note: 10M rows in memory might be tight depending on environment,
        # but we'll try for the benchmark sake.
        try:
            mem_res = run_test(path, n, streaming=False, batch_size=args.batch_size)
            print(
                f"{n:<12,}| {'In-Mem':<10} | {mem_res['duration']:>8.2f} s | "
                f"{mem_res['rows_per_sec']:>8,.0f} | "
                f"{mem_res['peak_memory_mib']:>8.1f} MiB"
            )
            results.append(mem_res)
        except Exception as e:
            print(f"{n:<12,}| {'In-Mem':<10} | FAILED: {e}")

        # Test 2: Streaming
        stream_res = run_test(path, n, streaming=True, batch_size=args.batch_size)
        print(
            f"{n:<12,}| {'Stream':<10} | {stream_res['duration']:>8.2f} s | "
            f"{stream_res['rows_per_sec']:>8,.0f} | "
            f"{stream_res['peak_memory_mib']:>8.1f} MiB"
        )
        results.append(stream_res)
        print("-" * 60)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
