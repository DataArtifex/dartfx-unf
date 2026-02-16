# SPDX-FileCopyrightText: 2024-present kulnor <pascal@codata.org>
#
# SPDX-License-Identifier: MIT

"""SHA-256 hashing and UNF fingerprint generation (spec §Ib and §II)."""

from __future__ import annotations

import base64
import hashlib

from dartfx.unf.parameters import UNFParameters


def compute_unf_hash(
    concatenated: bytes,
    params: UNFParameters | None = None,
) -> str:
    """Compute the UNF fingerprint from a concatenated byte string.

    This implements spec §Ib:
    1. Compute SHA-256 of the concatenated normalized values.
    2. Truncate the hash to ``H`` bits (default 128).
    3. Encode the result in base64.
    4. Prepend the UNF header.

    Parameters
    ----------
    concatenated : bytes
        The concatenated, normalized byte representations of all
        vector elements.
    params : UNFParameters, optional
        Calculation parameters. Uses defaults if not provided.

    Returns
    -------
    str
        The printable UNF string, e.g. ``UNF:6:Do5dfAoOOFt4FSj0JcByEw==``.
    """
    if params is None:
        params = UNFParameters()

    sha256_digest = hashlib.sha256(concatenated).digest()

    # Truncate to H bits
    truncated_bytes = params.hash_bits // 8
    truncated_hash = sha256_digest[:truncated_bytes]

    encoded = base64.b64encode(truncated_hash).decode("ascii")

    return params.header + encoded


def finalize_hash(
    hasher: hashlib._Hash,  # noqa: SLF001
    params: UNFParameters | None = None,
) -> str:
    """Produce a UNF string from an in-progress SHA-256 hasher.

    This is the incremental counterpart of :func:`compute_unf_hash`.
    Feed normalized bytes into the *hasher* via ``hasher.update(chunk)``
    across one or more batches, then call this function once to obtain
    the final UNF string.

    Parameters
    ----------
    hasher : hashlib._Hash
        A SHA-256 hash object (from ``hashlib.sha256()``).
    params : UNFParameters, optional
        Calculation parameters. Uses defaults if not provided.

    Returns
    -------
    str
        The printable UNF string.
    """
    if params is None:
        params = UNFParameters()

    digest = hasher.digest()
    truncated_bytes = params.hash_bits // 8
    truncated_hash = digest[:truncated_bytes]
    encoded = base64.b64encode(truncated_hash).decode("ascii")
    return params.header + encoded


def combine_unfs(unf_strings: list[str], params: UNFParameters | None = None) -> str:
    """Combine multiple UNF strings into a single UNF (spec §IIa / §IIb).

    The UNF specification requires:
    1. Sort the printable UNF strings in POSIX locale order.
    2. Apply the UNF algorithm to the resulting vector of character strings.

    Parameters
    ----------
    unf_strings : list[str]
        List of printable UNF strings to combine.
    params : UNFParameters, optional
        Calculation parameters. Uses defaults if not provided.

    Returns
    -------
    str
        The combined UNF string.
    """
    if params is None:
        params = UNFParameters()

    if len(unf_strings) == 1:
        return unf_strings[0]

    # Sort in POSIX locale order (byte-level sort of UTF-8 strings)
    sorted_unfs = sorted(unf_strings)

    # Treat each UNF string as a character string value:
    # encode as UTF-8, terminate with \n\0, then concatenate.
    concatenated = b""
    for unf_str in sorted_unfs:
        concatenated += unf_str.encode("utf-8") + b"\n\x00"

    return compute_unf_hash(concatenated, params)
