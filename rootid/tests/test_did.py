"""Tests for ``rootid/did.py``.

Pins the ``did:knx:`` method shape from spec Section 5 + W3C DID Core.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from hypothesis import given
from hypothesis import settings as hsettings
from hypothesis import strategies as st
from pydantic import ValidationError

from core.config import ED25519_PUBLIC_BYTES
from rootid import did

# ---------------------------------------------------------------------------
# make_did
# ---------------------------------------------------------------------------


class TestMakeDid:
    def test_format(self) -> None:
        pub = b"\x01" * ED25519_PUBLIC_BYTES
        out = did.make_did("testnet", pub)
        assert out.startswith("did:knx:testnet:")
        # Identifier is the first 16 hex chars of SHA-3-256 of pub.
        assert len(out.split(":")[-1]) == 16

    def test_deterministic(self) -> None:
        pub = b"\x02" * ED25519_PUBLIC_BYTES
        assert did.make_did("mainnet", pub) == did.make_did("mainnet", pub)

    def test_distinct_keys_produce_distinct_dids(self) -> None:
        pub1 = b"\x01" * ED25519_PUBLIC_BYTES
        pub2 = b"\x02" * ED25519_PUBLIC_BYTES
        assert did.make_did("testnet", pub1) != did.make_did("testnet", pub2)

    def test_distinct_networks_produce_distinct_dids(self) -> None:
        pub = b"\x03" * ED25519_PUBLIC_BYTES
        assert did.make_did("mainnet", pub) != did.make_did("testnet", pub)

    def test_rejects_wrong_pubkey_length(self) -> None:
        with pytest.raises(ValueError, match="32 bytes"):
            did.make_did("testnet", b"\x00" * 31)

    def test_rejects_empty_network(self) -> None:
        with pytest.raises(ValueError, match="network"):
            did.make_did("", b"\x00" * ED25519_PUBLIC_BYTES)

    def test_rejects_network_with_invalid_chars(self) -> None:
        # Network must be alphanumeric, dot, hyphen, underscore — no colons
        # (colon is the DID delimiter and would break parse_did).
        with pytest.raises(ValueError, match="network"):
            did.make_did("test:net", b"\x00" * ED25519_PUBLIC_BYTES)

    def test_result_matches_spec_pattern(self) -> None:
        pub = b"\x04" * ED25519_PUBLIC_BYTES
        out = did.make_did("testnet", pub)
        assert did.DID_PATTERN.match(out) is not None

    @given(
        network=st.sampled_from(["mainnet", "testnet", "devnet", "local"]),
        pub=st.binary(min_size=32, max_size=32),
    )
    @hsettings(max_examples=50, deadline=None)
    def test_make_did_property(self, network: str, pub: bytes) -> None:
        out = did.make_did(network, pub)
        assert did.DID_PATTERN.match(out) is not None
        assert out.split(":")[2] == network


# ---------------------------------------------------------------------------
# parse_did
# ---------------------------------------------------------------------------


class TestParseDid:
    def test_round_trip(self) -> None:
        pub = b"\x05" * ED25519_PUBLIC_BYTES
        d = did.make_did("testnet", pub)
        network, identifier = did.parse_did(d)
        assert network == "testnet"
        assert len(identifier) == 16

    def test_rejects_non_knx_method(self) -> None:
        with pytest.raises(ValueError, match="did:knx:"):
            did.parse_did("did:example:abc")

    def test_rejects_no_did_prefix(self) -> None:
        with pytest.raises(ValueError, match="did:knx:"):
            did.parse_did("knx:testnet:abc")

    def test_rejects_missing_identifier(self) -> None:
        with pytest.raises(ValueError, match="identifier"):
            did.parse_did("did:knx:testnet:")

    def test_rejects_wrong_part_count_too_few(self) -> None:
        with pytest.raises(ValueError, match="four colon-separated"):
            did.parse_did("did:knx:testnet")

    def test_rejects_wrong_part_count_too_many(self) -> None:
        with pytest.raises(ValueError, match="four colon-separated"):
            did.parse_did("did:knx:testnet:abc:xyz")

    def test_rejects_missing_network(self) -> None:
        with pytest.raises(ValueError, match="network"):
            did.parse_did("did:knx::abc")


# ---------------------------------------------------------------------------
# build_did_document
# ---------------------------------------------------------------------------


class TestBuildDidDocument:
    def test_returns_valid_pydantic_model(self) -> None:
        pub = b"\x06" * ED25519_PUBLIC_BYTES
        auth = b"\x07" * ED25519_PUBLIC_BYTES
        d = did.make_did("testnet", pub)
        doc = did.build_did_document(
            d,
            public_bytes=pub,
            auth_bytes=auth,
            capabilities=["camera", "imu"],
            created_at=datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc),
        )
        assert doc.id == d
        assert doc.public_key_hex == pub.hex()
        assert doc.auth_key_hex == auth.hex()
        assert doc.capabilities == ["camera", "imu"]

    def test_pydantic_validation_runs(self) -> None:
        # Passing a malformed DID surfaces ValidationError from the
        # underlying DIDDocument model — we don't silently re-pattern.
        with pytest.raises((ValidationError, ValueError)):
            did.build_did_document(
                "not-a-did",
                public_bytes=b"\x00" * 32,
                auth_bytes=b"\x00" * 32,
                capabilities=[],
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )

    def test_rejects_wrong_pubkey_length(self) -> None:
        with pytest.raises(ValueError, match="32 bytes"):
            did.build_did_document(
                "did:knx:testnet:abc",
                public_bytes=b"\x00" * 31,
                auth_bytes=b"\x00" * 32,
                capabilities=[],
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )

    def test_rejects_wrong_auth_key_length(self) -> None:
        with pytest.raises(ValueError, match="32 bytes"):
            did.build_did_document(
                "did:knx:testnet:abc",
                public_bytes=b"\x00" * 32,
                auth_bytes=b"\x00" * 33,
                capabilities=[],
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
