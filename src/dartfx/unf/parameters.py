# SPDX-FileCopyrightText: 2024-present kulnor <pascal@codata.org>
#
# SPDX-License-Identifier: MIT

"""UNF calculation parameters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UNFParameters:
    """Parameters controlling the Universal Number Fingerprint (UNF) v6 calculation.

    This class encapsulates all the optional parameters defined in the UNF v6
    specification. When non-default values are used, they are automatically
    encoded into the resulting UNF header string (e.g., ``UNF:6:N9:...``).

    Examples
    --------
    >>> from dartfx.unf.parameters import UNFParameters
    >>> # Standard v6 defaults
    >>> params = UNFParameters()
    >>> print(params.header)
    UNF:6:

    >>> # High precision (9 digits) and larger hash (256 bits)
    >>> params = UNFParameters(digits=9, hash_bits=256)
    >>> print(params.header)
    UNF:6:N9,H256:

    >>> # Use truncation (R1) mode
    >>> params = UNFParameters(truncate=True)
    >>> print(params.header)
    UNF:6:R1:
    """

    digits: int = 7
    characters: int = 128
    hash_bits: int = 128
    truncate: bool = False

    def __post_init__(self) -> None:
        if self.digits < 1:
            msg = f"digits must be >= 1, got {self.digits}"
            raise ValueError(msg)
        if self.characters < 1:
            msg = f"characters must be >= 1, got {self.characters}"
            raise ValueError(msg)
        if self.hash_bits not in (128, 192, 196, 256):
            msg = (
                f"hash_bits must be one of {{128, 192, 196, 256}}, got {self.hash_bits}"
            )
            raise ValueError(msg)

    @property
    def is_default(self) -> bool:
        """Return True if all parameters are at their default values."""
        return (
            self.digits == 7
            and self.characters == 128
            and self.hash_bits == 128
            and not self.truncate
        )

    @property
    def header(self) -> str:
        """Build the UNF header string, e.g. ``UNF:6:`` or ``UNF:6:N9,H256:``."""
        parts: list[str] = []
        if self.digits != 7:
            parts.append(f"N{self.digits}")
        if self.characters != 128:
            parts.append(f"X{self.characters}")
        if self.hash_bits != 128:
            parts.append(f"H{self.hash_bits}")
        if self.truncate:
            parts.append("R1")
        if parts:
            return f"UNF:6:{','.join(parts)}:"
        return "UNF:6:"
