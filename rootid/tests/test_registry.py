"""Tests for ``rootid/registry.py``."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from rootid.did import build_did_document, make_did
from rootid.registry import IdentityRegistry, IdentityRegistryError


def _doc(public_bytes: bytes, *, network: str = "testnet") -> tuple[str, object]:
    auth = bytes(b ^ 0xFF for b in public_bytes)  # different bytes
    did_str = make_did(network, public_bytes)
    doc = build_did_document(
        did_str,
        public_bytes=public_bytes,
        auth_bytes=auth,
        capabilities=["camera"],
        created_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
    )
    return did_str, doc


class TestIdentityRegistry:
    def test_register_then_resolve(self) -> None:
        reg = IdentityRegistry()
        pub = b"\x01" * 32
        did_str, doc = _doc(pub)
        reg.register(doc)  # type: ignore[arg-type]
        assert reg.resolve(did_str) == doc
        assert did_str in reg

    def test_unknown_did_raises(self) -> None:
        reg = IdentityRegistry()
        with pytest.raises(KeyError):
            reg.resolve("did:knx:testnet:deadbeefdeadbeef")

    def test_public_key_for_returns_bytes(self) -> None:
        reg = IdentityRegistry()
        pub = b"\x02" * 32
        did_str, doc = _doc(pub)
        reg.register(doc)  # type: ignore[arg-type]
        assert reg.public_key_for(did_str) == pub

    def test_duplicate_did_same_key_idempotent(self) -> None:
        reg = IdentityRegistry()
        pub = b"\x03" * 32
        did_str, doc = _doc(pub)
        reg.register(doc)  # type: ignore[arg-type]
        reg.register(doc)  # type: ignore[arg-type]  # no-op
        assert reg.public_key_for(did_str) == pub

    def test_duplicate_did_different_key_rejected(self) -> None:
        # Mirrors RobotIdentity contract: a DID's pubkey is immutable on-chain.
        reg = IdentityRegistry()
        pub_a = b"\x04" * 32
        pub_b = b"\x05" * 32
        # Force same DID via test seam: use the same public bytes for the
        # identifier hash but a "different" doc by tweaking auth_bytes only.
        # Simpler: reuse the same DID string with a freshly built doc that
        # has a different public_key_hex.
        did_str, doc_a = _doc(pub_a)
        # Construct doc_b that lies and claims pub_b for the same DID.
        from core.models import DIDDocument

        doc_b = DIDDocument(
            id=did_str,
            public_key_hex=pub_b.hex(),
            auth_key_hex=("aa" * 32),
            capabilities=[],
            created_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
        )
        reg.register(doc_a)  # type: ignore[arg-type]
        with pytest.raises(IdentityRegistryError, match="already registered"):
            reg.register(doc_b)

    def test_membership_negative(self) -> None:
        reg = IdentityRegistry()
        assert "did:knx:testnet:nope" not in reg

    def test_register_rejects_malformed_pubkey_hex(self) -> None:
        from core.models import DIDDocument

        bad = DIDDocument(
            id="did:knx:testnet:abc",
            public_key_hex="zz" * 32,  # not valid hex
            auth_key_hex="aa" * 32,
            capabilities=[],
            created_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
        )
        reg = IdentityRegistry()
        with pytest.raises(IdentityRegistryError, match="public_key_hex"):
            reg.register(bad)

    def test_register_rejects_wrong_pubkey_length(self) -> None:
        from core.models import DIDDocument

        bad = DIDDocument(
            id="did:knx:testnet:abc",
            public_key_hex="aa" * 31,  # 31 bytes, wrong length
            auth_key_hex="aa" * 32,
            capabilities=[],
            created_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
        )
        reg = IdentityRegistry()
        with pytest.raises(IdentityRegistryError, match="32 bytes"):
            reg.register(bad)
