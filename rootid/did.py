"""``did:knx:`` method — DID construction, parsing, and document building.

The ``did:knx:`` DID method is W3C-DID-Core-compliant. The identifier is
deterministic over the robot's Ed25519 public key (truncated SHA-3-256
of the key bytes), so two robots with the same key collapse to the same
identifier — the registry refuses to attach distinct documents to the
same identifier (see ``rootid.registry``).

Format::

    did:knx:<network>:<identifier>

* ``network`` ∈ {``mainnet``, ``testnet``, ``devnet``, ...}; alphanumeric
  plus ``-``, ``_``, ``.`` (no colons; no whitespace).
* ``identifier`` is the first 16 hex characters of
  ``sha3_256(public_bytes)`` — 64 bits of collision resistance for the
  identifier alone, with the full key continuing to authenticate
  signatures.

Spec reference: build spec §5 + https://www.w3.org/TR/did-core/.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from core.config import ED25519_PUBLIC_BYTES
from core.crypto import sha3_256
from core.models import DIDDocument

if TYPE_CHECKING:
    from datetime import datetime

#: Compiled DID regex per spec Section 5.
DID_PATTERN: re.Pattern[str] = re.compile(r"^did:knx:[a-zA-Z0-9_:.-]+$")

#: Per-segment network regex — stricter than ``DID_PATTERN`` because the
#: full DID matches across segments. Used to validate the ``network``
#: argument before assembly so we never produce a DID that ``parse_did``
#: would reject.
_NETWORK_PATTERN: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9_.-]+$")

#: Length of the truncated identifier, in hex characters.
_IDENTIFIER_HEX_LEN: int = 16

#: Number of colon-separated parts in a well-formed ``did:knx:`` string:
#: ``("did", "knx", network, identifier)``.
_DID_PART_COUNT: int = 4


def make_did(network: str, public_bytes: bytes) -> str:
    """Construct a ``did:knx:`` identifier.

    Args:
        network: Network namespace, e.g. ``"testnet"`` or ``"mainnet"``.
            Must match ``[a-zA-Z0-9_.-]+`` (no colons, no whitespace).
        public_bytes: 32-byte Ed25519 public key.

    Returns:
        ``did:knx:<network>:<identifier>``.

    Raises:
        ValueError: If ``network`` is empty / malformed, or
            ``public_bytes`` is not exactly 32 bytes.
    """
    if not network:
        msg = "network must be a non-empty string"
        raise ValueError(msg)
    if not _NETWORK_PATTERN.fullmatch(network):
        msg = (
            "network must match [a-zA-Z0-9_.-]+ "
            "(no colons, no whitespace, no leading/trailing dots)"
        )
        raise ValueError(msg)
    if len(public_bytes) != ED25519_PUBLIC_BYTES:
        msg = f"public_bytes must be {ED25519_PUBLIC_BYTES} bytes, got {len(public_bytes)}"
        raise ValueError(msg)
    identifier = sha3_256(public_bytes).hex()[:_IDENTIFIER_HEX_LEN]
    return f"did:knx:{network}:{identifier}"


def parse_did(did_str: str) -> tuple[str, str]:
    """Parse a ``did:knx:`` identifier into ``(network, identifier)``.

    Raises:
        ValueError: If ``did_str`` does not start with ``did:knx:`` or
            has missing components.
    """
    if not did_str.startswith("did:knx:"):
        msg = f"DID must start with 'did:knx:', got {did_str!r}"
        raise ValueError(msg)
    parts = did_str.split(":")
    if len(parts) != _DID_PART_COUNT:
        msg = f"DID must have exactly four colon-separated parts, got {did_str!r}"
        raise ValueError(msg)
    _, _, network, identifier = parts
    if not network:
        msg = f"DID network segment is empty: {did_str!r}"
        raise ValueError(msg)
    if not identifier:
        msg = f"DID identifier segment is empty: {did_str!r}"
        raise ValueError(msg)
    return network, identifier


def build_did_document(
    did_str: str,
    *,
    public_bytes: bytes,
    auth_bytes: bytes,
    capabilities: list[str],
    created_at: datetime,
) -> DIDDocument:
    """Compose a Pydantic-validated ``DIDDocument``.

    Args:
        did_str: A pre-built ``did:knx:`` identifier.
        public_bytes: 32-byte signing key.
        auth_bytes: 32-byte authentication key (separate from
            ``public_bytes`` so signing and command authorization can
            be rotated independently).
        capabilities: Sensor capabilities, e.g. ``["camera", "imu"]``.
        created_at: Timezone-aware UTC creation time.

    Returns:
        A validated ``core.models.DIDDocument``.

    Raises:
        ValueError: If either key is the wrong length (raised before
            constructing the model so the caller gets a clear message
            rather than a generic Pydantic complaint about hex strings).
        pydantic.ValidationError: If ``did_str`` does not match the
            spec pattern.
    """
    if len(public_bytes) != ED25519_PUBLIC_BYTES:
        msg = f"public_bytes must be {ED25519_PUBLIC_BYTES} bytes, got {len(public_bytes)}"
        raise ValueError(msg)
    if len(auth_bytes) != ED25519_PUBLIC_BYTES:
        msg = f"auth_bytes must be {ED25519_PUBLIC_BYTES} bytes, got {len(auth_bytes)}"
        raise ValueError(msg)
    return DIDDocument(
        id=did_str,
        public_key_hex=public_bytes.hex(),
        auth_key_hex=auth_bytes.hex(),
        capabilities=list(capabilities),
        created_at=created_at,
    )
