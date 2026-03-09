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


def _strip_unf_header(unf_string: str) -> str:
    """Extract the base64 hash portion from a printable UNF string.

    The canonical Java reference implementation (``UnfDigest.addUNFs``)
    strips the ``UNF:`` prefix and any version/parameter tokens before
    combining column UNFs into a file-level UNF.  For example::

        "UNF:6:AvELPR5QTaBbnq6S22Msow=="  →  "AvELPR5QTaBbnq6S22Msow=="
        "UNF:6:N9:IKw+l4ywdwsJeDze8dplJA=="  →  "IKw+l4ywdwsJeDze8dplJA=="

    This function mirrors that behaviour by splitting on ``":"`` and
    returning the last segment, which is always the base64-encoded hash.

    Parameters
    ----------
    unf_string : str
        A full printable UNF string (e.g. ``UNF:6:hash==``).

    Returns
    -------
    str
        The bare base64 hash component.
    """
    # Split on ":" — the last element is always the base64 hash.
    # "UNF:6:hash=="       → ["UNF", "6", "hash=="]       → "hash=="
    # "UNF:6:N9,H256:hash==" → ["UNF", "6", "N9,H256", "hash=="] → "hash=="
    parts = unf_string.split(":")
    if len(parts) >= 3 and unf_string.startswith("UNF:"):
        return parts[-1].strip()
    return parts[0].strip()


def combine_unfs(unf_strings: list[str], params: UNFParameters | None = None) -> str:
    """Combine multiple UNF strings into a single UNF (spec §IIa / §IIb).

    Implements the combination algorithm for higher-level UNF objects:

    1. **Strip** the ``UNF:6:`` header from each individual UNF, keeping
       only the base64 hash component.
    2. **Sort** the stripped hashes in POSIX locale order (byte-level).
    3. **Apply** the UNF character-string algorithm (UTF-8 encode, terminate
       with ``\\n\\0``, concatenate, SHA-256 hash).

    .. note::

       The UNF v6 specification text says to sort "the printable UTF-8
       representations of the individual UNFs", which could be read as
       using the full ``UNF:6:...`` strings.  However, the canonical Java
       reference implementation (``UnfDigest.addUNFs`` in the Dataverse
       UNF library) strips the header before combining.  This
       implementation follows the Java behaviour to ensure
       interoperability with the Dataverse ecosystem and all existing
       UNF signatures produced by it.

       See: https://github.com/IQSS/UNF  (``UnfDigest.addUNFs``)

    Parameters
    ----------
    unf_strings : list[str]
        List of printable UNF strings to combine (e.g.
        ``["UNF:6:abc==", "UNF:6:xyz=="]``).
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

    # Strip the UNF header from each string, keeping only the base64 hash.
    # This matches the canonical Java implementation (UnfDigest.addUNFs)
    # which splits on ":" and takes the last segment before sorting.
    stripped = [_strip_unf_header(s) for s in unf_strings]

    # Sort in POSIX locale order (byte-level sort of UTF-8 strings)
    sorted_hashes = sorted(stripped)

    # Treat each hash as a character string value:
    # encode as UTF-8, terminate with \n\0, then concatenate.
    concatenated = b""
    for hash_str in sorted_hashes:
        concatenated += hash_str.encode("utf-8") + b"\n\x00"

    return compute_unf_hash(concatenated, params)
