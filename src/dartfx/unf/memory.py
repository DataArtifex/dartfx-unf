# SPDX-FileCopyrightText: 2024-present kulnor <pascal@codata.org>
#
# SPDX-License-Identifier: MIT

"""System memory utilities for streaming decision-making.

Provides platform-aware memory detection and a heuristic to decide
whether a file should be processed in-memory or via streaming.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Default memory budget when detection fails (4 GB).
_FALLBACK_MEMORY_BYTES = 4 * 1024**3

# In-memory DataFrames typically require 2–5× the raw file size.
# We compare file size against this fraction of available memory.
_DEFAULT_MEMORY_FRACTION = 0.25


def get_available_memory() -> int:
    """Estimate available system memory in bytes.

    Strategy (in order of preference):

    1. Linux ``/proc/meminfo`` – reads *MemAvailable*, which accounts
       for caches and buffers and is the most accurate indicator of
       how much memory a new process can use.
    2. Windows ``kernel32.GlobalMemoryStatusEx`` – returns *available*
       physical memory via the Win32 API (no external dependencies).
    3. ``os.sysconf`` – available on macOS and Linux; returns *total*
       physical memory (not currently-free memory, but still useful
       as an upper bound).
    4. Fallback – assume 4 GB.

    Returns
    -------
    int
        Estimated available memory in bytes.
    """
    # --- Linux: /proc/meminfo (best source) ---
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    # Value is in kB
                    return int(line.split()[1]) * 1024
    except (FileNotFoundError, OSError, ValueError):
        pass

    # --- Windows: kernel32.GlobalMemoryStatusEx ---
    try:
        import ctypes
        import ctypes.wintypes

        class MEMORYSTATUSEX(ctypes.Structure):  # noqa: N801
            _fields_ = [
                ("dwLength", ctypes.wintypes.DWORD),
                ("dwMemoryLoad", ctypes.wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):  # type: ignore[attr-defined]
            return int(stat.ullAvailPhys)
    except (AttributeError, OSError, ImportError):
        # AttributeError: ctypes.windll doesn't exist on non-Windows
        pass

    # --- macOS / Linux: os.sysconf (total physical memory) ---
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        if pages > 0 and page_size > 0:
            return pages * page_size
    except (ValueError, OSError, AttributeError):
        pass

    logger.warning(
        "Could not detect system memory; defaulting to %d MB",
        _FALLBACK_MEMORY_BYTES // (1024 * 1024),
    )
    return _FALLBACK_MEMORY_BYTES


def should_stream(
    file_path: Path,
    *,
    memory_fraction: float = _DEFAULT_MEMORY_FRACTION,
) -> bool:
    """Decide whether a file should be processed via streaming.

    The heuristic compares the on-disk file size against a configurable
    fraction of available memory.  Because in-memory representations
    (especially for CSV) can be several times larger than the raw file,
    the default fraction is conservative (25 %).

    Parameters
    ----------
    file_path : Path
        Path to the data file.
    memory_fraction : float
        Fraction of available memory above which streaming is triggered.
        Default is 0.25 (25 %).

    Returns
    -------
    bool
        ``True`` if streaming is recommended.
    """
    file_size = file_path.stat().st_size
    available = get_available_memory()
    threshold = int(available * memory_fraction)
    use_streaming = file_size > threshold

    logger.info(
        "File %s: %.1f MB | Available memory: %.1f MB | "
        "Threshold (%.0f%%): %.1f MB | Mode: %s",
        file_path.name,
        file_size / (1024 * 1024),
        available / (1024 * 1024),
        memory_fraction * 100,
        threshold / (1024 * 1024),
        "streaming" if use_streaming else "in-memory",
    )

    return use_streaming
