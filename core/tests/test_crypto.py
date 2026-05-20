"""Crypto primitive tests.

Sources of truth:

* RFC 8032 §7.1 (Ed25519 test vectors): https://datatracker.ietf.org/doc/html/rfc8032#section-7.1
* FIPS 202 / NIST CAVS SHA-3-256 short-message vectors:
  https://csrc.nist.gov/projects/cryptographic-algorithm-validation-program/secure-hashing
* RFC 6962 §2.1 (Merkle hash for empty list).

All vectors are pasted verbatim. If a value below disagrees with the
upstream document, the upstream document is correct and this file is wrong.
"""

from __future__ import annotations

import hashlib

import pytest
from hypothesis import given
from hypothesis import settings as hsettings
from hypothesis import strategies as st

from core import crypto
from core.config import (
    ED25519_PRIVATE_BYTES,
    ED25519_PUBLIC_BYTES,
    ED25519_SIGNATURE_BYTES,
    SHA3_256_BYTES,
)

# ---------------------------------------------------------------------------
# RFC 8032 Ed25519 test vectors (§7.1, "TEST 1" and "TEST 2")
# ---------------------------------------------------------------------------

# TEST 1
RFC8032_TEST1_SECRET = bytes.fromhex(
    "9d61b19deffd5a60ba844af492ec2cc4" "4449c5697b326919703bac031cae7f60",
)
RFC8032_TEST1_PUBLIC = bytes.fromhex(
    "d75a980182b10ab7d54bfed3c964073a" "0ee172f3daa62325af021a68f707511a",
)
RFC8032_TEST1_MESSAGE = b""
RFC8032_TEST1_SIGNATURE = bytes.fromhex(
    "e5564300c360ac729086e2cc806e828a"
    "84877f1eb8e5d974d873e06522490155"
    "5fb8821590a33bacc61e39701cf9b46b"
    "d25bf5f0595bbe24655141438e7a100b",
)

# TEST 2
RFC8032_TEST2_SECRET = bytes.fromhex(
    "4ccd089b28ff96da9db6c346ec114e0f" "5b8a319f35aba624da8cf6ed4fb8a6fb",
)
RFC8032_TEST2_PUBLIC = bytes.fromhex(
    "3d4017c3e843895a92b70aa74d1b7ebc" "9c982ccf2ec4968cc0cd55f12af4660c",
)
RFC8032_TEST2_MESSAGE = bytes.fromhex("72")
RFC8032_TEST2_SIGNATURE = bytes.fromhex(
    "92a009a9f0d4cab8720e820b5f642540"
    "a2b27b5416503f8fb3762223ebdb69da"
    "085ac1e43e15996e458f3613d0f11d8c"
    "387b2eaeb4302aeeb00d291612bb0c00",
)


class TestEd25519:
    """Validate against RFC 8032 §7.1 known vectors."""

    def test_keypair_sizes(self) -> None:
        priv, pub = crypto.generate_keypair()
        assert len(priv) == ED25519_PRIVATE_BYTES
        assert len(pub) == ED25519_PUBLIC_BYTES

    def test_keypair_distinct_each_call(self) -> None:
        priv1, pub1 = crypto.generate_keypair()
        priv2, pub2 = crypto.generate_keypair()
        assert priv1 != priv2
        assert pub1 != pub2

    def test_sign_rfc8032_test1_empty_message(self) -> None:
        sig = crypto.sign(RFC8032_TEST1_SECRET, RFC8032_TEST1_MESSAGE)
        assert sig == RFC8032_TEST1_SIGNATURE
        assert len(sig) == ED25519_SIGNATURE_BYTES

    def test_sign_rfc8032_test2_one_byte_message(self) -> None:
        sig = crypto.sign(RFC8032_TEST2_SECRET, RFC8032_TEST2_MESSAGE)
        assert sig == RFC8032_TEST2_SIGNATURE

    def test_verify_rfc8032_test1(self) -> None:
        assert crypto.verify(
            RFC8032_TEST1_PUBLIC,
            RFC8032_TEST1_MESSAGE,
            RFC8032_TEST1_SIGNATURE,
        )

    def test_verify_rfc8032_test2(self) -> None:
        assert crypto.verify(
            RFC8032_TEST2_PUBLIC,
            RFC8032_TEST2_MESSAGE,
            RFC8032_TEST2_SIGNATURE,
        )

    def test_verify_rejects_tampered_signature(self) -> None:
        bad = bytearray(RFC8032_TEST1_SIGNATURE)
        bad[0] ^= 0x01
        assert not crypto.verify(
            RFC8032_TEST1_PUBLIC,
            RFC8032_TEST1_MESSAGE,
            bytes(bad),
        )

    def test_verify_rejects_tampered_message(self) -> None:
        assert not crypto.verify(
            RFC8032_TEST1_PUBLIC,
            b"different",
            RFC8032_TEST1_SIGNATURE,
        )

    def test_verify_rejects_wrong_public_key(self) -> None:
        wrong_pub = RFC8032_TEST2_PUBLIC
        assert not crypto.verify(
            wrong_pub,
            RFC8032_TEST1_MESSAGE,
            RFC8032_TEST1_SIGNATURE,
        )

    def test_verify_rejects_malformed_signature_length(self) -> None:
        assert not crypto.verify(
            RFC8032_TEST1_PUBLIC,
            b"x",
            b"\x00" * 63,
        )

    def test_verify_rejects_malformed_public_key_length(self) -> None:
        assert not crypto.verify(b"\x00" * 31, b"x", b"\x00" * 64)

    def test_verify_rejects_identity_public_key(self) -> None:
        # The all-zero 32-byte string is the canonical encoding of the
        # curve's identity element. Vanilla RFC 8032 verifiers accept it
        # as a public key and the all-zero signature trivially satisfies
        # S·B = R + H(...)·A when A = 0, S = 0, R = 0. We reject this
        # weak-key class explicitly (see core/crypto.py docstring).
        for sig_byte in (b"\x00", b"\xff", b"\x42"):
            assert not crypto.verify(
                b"\x00" * 32,
                b"any message",
                sig_byte * 64,
            )

    @given(message=st.binary(min_size=0, max_size=4096))
    @hsettings(max_examples=50, deadline=None)
    def test_sign_verify_roundtrip(self, message: bytes) -> None:
        priv, pub = crypto.generate_keypair()
        sig = crypto.sign(priv, message)
        assert crypto.verify(pub, message, sig)

    @given(
        message=st.binary(min_size=0, max_size=64),
        flip_index=st.integers(min_value=0, max_value=63),
    )
    @hsettings(max_examples=25, deadline=None)
    def test_sign_then_corrupt_signature_fails(
        self,
        message: bytes,
        flip_index: int,
    ) -> None:
        priv, pub = crypto.generate_keypair()
        sig = bytearray(crypto.sign(priv, message))
        sig[flip_index] ^= 0x80
        assert not crypto.verify(pub, message, bytes(sig))


# ---------------------------------------------------------------------------
# SHA-3-256 known vectors
# ---------------------------------------------------------------------------


class TestSha3:
    """Validate sha3_256 against well-known FIPS 202 vectors."""

    def test_empty_string(self) -> None:
        # SHA3-256("") = a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a
        expected = bytes.fromhex(
            "a7ffc6f8bf1ed76651c14756a061d662" "f580ff4de43b49fa82d80a4b80f8434a",
        )
        assert crypto.sha3_256(b"") == expected
        assert len(crypto.sha3_256(b"")) == SHA3_256_BYTES

    def test_abc(self) -> None:
        # SHA3-256("abc") = 3a985da74fe225b2045c172d6bd390bd855f086e3e9d525b46bfe24511431532
        expected = bytes.fromhex(
            "3a985da74fe225b2045c172d6bd390bd" "855f086e3e9d525b46bfe24511431532",
        )
        assert crypto.sha3_256(b"abc") == expected

    def test_matches_hashlib(self) -> None:
        msg = b"konnexcore"
        assert crypto.sha3_256(msg) == hashlib.sha3_256(msg).digest()

    @given(data=st.binary(min_size=0, max_size=8192))
    @hsettings(max_examples=100, deadline=None)
    def test_matches_hashlib_property(self, data: bytes) -> None:
        assert crypto.sha3_256(data) == hashlib.sha3_256(data).digest()

    @given(data=st.binary(min_size=0, max_size=1024))
    @hsettings(max_examples=50, deadline=None)
    def test_output_size_invariant(self, data: bytes) -> None:
        assert len(crypto.sha3_256(data)) == SHA3_256_BYTES


# ---------------------------------------------------------------------------
# Merkle root tests
# ---------------------------------------------------------------------------


class TestMerkleRoot:
    """Validate merkle_root against constructed cases."""

    def test_empty_returns_sha3_of_empty(self) -> None:
        # Convention: empty Merkle root = SHA-3-256(b""). Documented in
        # core/crypto.py docstring; mirrors RFC 6962 §2.1 spirit (with
        # SHA-3 substituted per Konnex protocol).
        assert crypto.merkle_root([]) == hashlib.sha3_256(b"").digest()

    def test_single_leaf_returns_hash_of_leaf(self) -> None:
        leaf = b"hello"
        assert crypto.merkle_root([leaf]) == hashlib.sha3_256(leaf).digest()

    def test_two_leaves_concatenates_then_hashes(self) -> None:
        a, b = b"a", b"b"
        h_a = hashlib.sha3_256(a).digest()
        h_b = hashlib.sha3_256(b).digest()
        expected = hashlib.sha3_256(h_a + h_b).digest()
        assert crypto.merkle_root([a, b]) == expected

    def test_three_leaves_pads_last(self) -> None:
        # Standard binary Merkle: odd-count level promotes (or
        # duplicates) the last hash. We use duplication (RFC 6962-style).
        a, b, c = b"a", b"b", b"c"
        h_a = hashlib.sha3_256(a).digest()
        h_b = hashlib.sha3_256(b).digest()
        h_c = hashlib.sha3_256(c).digest()
        h_ab = hashlib.sha3_256(h_a + h_b).digest()
        h_cc = hashlib.sha3_256(h_c + h_c).digest()
        expected = hashlib.sha3_256(h_ab + h_cc).digest()
        assert crypto.merkle_root([a, b, c]) == expected

    def test_four_leaves_balanced(self) -> None:
        leaves = [b"a", b"b", b"c", b"d"]
        h = [hashlib.sha3_256(x).digest() for x in leaves]
        h_ab = hashlib.sha3_256(h[0] + h[1]).digest()
        h_cd = hashlib.sha3_256(h[2] + h[3]).digest()
        expected = hashlib.sha3_256(h_ab + h_cd).digest()
        assert crypto.merkle_root(leaves) == expected

    def test_root_changes_when_leaf_changes(self) -> None:
        original = crypto.merkle_root([b"a", b"b", b"c", b"d"])
        tampered = crypto.merkle_root([b"a", b"b", b"c", b"D"])
        assert original != tampered

    def test_root_changes_when_leaf_order_changes(self) -> None:
        ab = crypto.merkle_root([b"a", b"b"])
        ba = crypto.merkle_root([b"b", b"a"])
        assert ab != ba

    @given(
        leaves=st.lists(
            st.binary(min_size=1, max_size=64),
            min_size=1,
            max_size=32,
        ),
    )
    @hsettings(max_examples=50, deadline=None)
    def test_root_is_deterministic(self, leaves: list[bytes]) -> None:
        assert crypto.merkle_root(leaves) == crypto.merkle_root(leaves)

    @given(
        leaves=st.lists(
            st.binary(min_size=1, max_size=64),
            min_size=1,
            max_size=32,
        ),
    )
    @hsettings(max_examples=50, deadline=None)
    def test_root_size_invariant(self, leaves: list[bytes]) -> None:
        assert len(crypto.merkle_root(leaves)) == SHA3_256_BYTES


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    """Crypto functions reject malformed inputs explicitly (fail-secure)."""

    def test_sign_rejects_short_private_key(self) -> None:
        with pytest.raises(ValueError, match="private key"):
            crypto.sign(b"\x00" * 31, b"x")

    def test_sign_rejects_long_private_key(self) -> None:
        with pytest.raises(ValueError, match="private key"):
            crypto.sign(b"\x00" * 33, b"x")

    def test_verify_returns_false_on_bad_input_does_not_raise(self) -> None:
        # verify() must never raise for malformed bytes — must return False
        # so callers can treat invalid signatures uniformly.
        assert crypto.verify(b"\x00" * 32, b"x", b"\x00" * 64) is False
