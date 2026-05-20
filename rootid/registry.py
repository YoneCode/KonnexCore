"""Mock ``RobotIdentity`` registry.

In production this is an on-chain contract per spec Section 6.3
(``Registry & Smart Contracts``). For Phase 1 we provide an in-memory
implementation with the same operational shape: register-then-resolve,
public-key authoritative for a given DID, immutable pubkey binding.

Threading: not thread-safe. Intended for single-process prototypes;
phase 6 wraps it behind a FastAPI dependency that serializes access
per request lifecycle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config import ED25519_PUBLIC_BYTES

if TYPE_CHECKING:
    from core.models import DIDDocument


class IdentityRegistryError(RuntimeError):
    """Registry-level invariant violation.

    Distinct from ``KeyError`` (raised by ``resolve`` for unknown DIDs)
    so callers can branch on "registry says no" vs "registry hasn't
    seen this DID".
    """


class IdentityRegistry:
    """In-memory mock of the on-chain ``RobotIdentity`` contract.

    Invariants:
        * A DID's public key is immutable once registered. A second
          ``register`` for the same DID with a different pubkey raises
          ``IdentityRegistryError``.
        * Re-registering with the same DID document is idempotent.
        * Pubkeys are stored only as 32-byte ``bytes`` — never hex strings —
          so callers cannot accidentally pass an ASCII representation
          to ``core.crypto.verify``.
    """

    def __init__(self) -> None:
        self._docs: dict[str, DIDDocument] = {}
        self._keys: dict[str, bytes] = {}

    def register(self, doc: DIDDocument) -> None:
        """Add a DID document to the registry.

        Raises:
            IdentityRegistryError: If ``doc.public_key_hex`` is not a
                32-byte hex string, or if the DID is already registered
                with a different public key.
        """
        try:
            pubkey = bytes.fromhex(doc.public_key_hex)
        except ValueError as exc:
            msg = f"public_key_hex is not valid hex: {doc.public_key_hex!r}"
            raise IdentityRegistryError(msg) from exc
        if len(pubkey) != ED25519_PUBLIC_BYTES:
            msg = (
                f"public key must be {ED25519_PUBLIC_BYTES} bytes, "
                f"got {len(pubkey)} for DID {doc.id}"
            )
            raise IdentityRegistryError(msg)

        existing = self._keys.get(doc.id)
        if existing is not None and existing != pubkey:
            msg = f"DID {doc.id} already registered with a different public key"
            raise IdentityRegistryError(msg)

        self._docs[doc.id] = doc
        self._keys[doc.id] = pubkey

    def resolve(self, did: str) -> DIDDocument:
        """Return the document registered for ``did``.

        Raises:
            KeyError: If ``did`` is not registered.
        """
        return self._docs[did]

    def public_key_for(self, did: str) -> bytes:
        """Return the 32-byte public key registered for ``did``.

        Raises:
            KeyError: If ``did`` is not registered.
        """
        return self._keys[did]

    def __contains__(self, did: object) -> bool:
        return isinstance(did, str) and did in self._keys
