"""Software-simulated Trusted Execution Environment.

This is the only place in KonnexCore where private key material is held
in process memory. Production deployments swap this module for a real
secure element binding — ARM PSA Crypto API, Apple Secure Enclave
Framework, or an equivalent — preserving the public surface defined
below.

PRODUCTION NOTE
---------------
Replace ``TEESimulator`` with hardware TEE bindings when leaving Spark
tier. The interface contract — ``__init__``, ``public_bytes``,
``robot_did``, ``sign_sensor_packet``, ``attest`` — is the swap-in
point. The hardware variant binds the same surface to a key that
genuinely cannot leave the secure element.

Security audit (per the ``zeroize-audit`` skill)
------------------------------------------------
* The private key is stored as ``self._private_bytes`` — single
  underscore prefix, attribute access only via ``_`` paths. Tests
  that need it ``# noqa: SLF001`` the access explicitly.
* ``_private_bytes`` is read in exactly two places: ``__init__``
  (assignment from ``core.crypto.generate_keypair``) and
  ``_sign_canonical_digest`` (the single signing site).
* Neither ``__repr__`` nor ``__str__`` ever serialise the private key.
* ``attest()`` returns only ``robot_did``, ``public_key_hex``, and the
  scheme tag ``"ed25519-sha3-256-v1"``.
* No logging in this module — neither private nor public material is
  written to a logger by the simulator. Callers that wish to audit
  signing events do so at their own layer.

Security audit (per the ``constant-time-analysis`` skill)
---------------------------------------------------------
* Signing goes through ``cryptography``'s
  ``Ed25519PrivateKey.sign``. The library is not documented as
  constant-time across all platforms, but the inputs to ``sign``
  here — the canonical digest — are publicly recomputable by anyone
  observing the packet, so timing leaks at the digest step do not
  expose the private key.
* The monotonic counter lookup is a Python ``dict`` access whose
  timing depends on the hash of ``(job_id, channel)``. Both inputs
  are public, so this leak is not security-relevant.

Threading
---------
The simulator is not thread-safe. The Konnex robot runtime runs one
capture pipeline per robot per process; concurrent capture is modelled
by separate ``TEESimulator`` instances for separate robots.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

from core import crypto
from core.config import ED25519_PRIVATE_BYTES, ED25519_PUBLIC_BYTES
from core.models import SensorPacket
from rootid.did import DID_PATTERN

if TYPE_CHECKING:
    from core.models import SensorChannel

#: Identifier for the canonical signing scheme used by this simulator.
#: Bumping this is the migration path if/when the canonical format
#: changes (cf. ``core.crypto.SENSOR_DOMAIN_V1``).
_SCHEME_TAG: str = "ed25519-sha3-256-v1"


class TEESimulator:
    """Software simulation of a per-robot Trusted Execution Environment."""

    def __init__(self, robot_did: str) -> None:
        """Generate a fresh keypair bound to ``robot_did``.

        Args:
            robot_did: A ``did:knx:`` identifier this simulator is
                authoritative for. The simulator does NOT verify that
                the DID was derived from its own public key — that's
                the registry's job (see ``rootid.registry``).

        Raises:
            ValueError: If ``robot_did`` is empty or does not match the
                ``did:knx:`` pattern.
        """
        if not robot_did:
            msg = "robot_did must be a non-empty did:knx: identifier"
            raise ValueError(msg)
        if DID_PATTERN.match(robot_did) is None:
            msg = f"robot_did must match did:knx: pattern, got {robot_did!r}"
            raise ValueError(msg)

        priv, pub = crypto.generate_keypair()
        # Defensive length checks — generate_keypair already guarantees
        # these, but the assertion documents the invariant.
        if len(priv) != ED25519_PRIVATE_BYTES or len(pub) != ED25519_PUBLIC_BYTES:
            msg = "generate_keypair returned wrong-length keys"  # pragma: no cover
            raise RuntimeError(msg)  # pragma: no cover

        self._private_bytes: bytes = priv
        self._public_bytes: bytes = pub
        self._robot_did: str = robot_did
        self._monotonic_counter: dict[tuple[str, str], int] = {}

    # ------------------------------------------------------------------
    # Read-only public surface
    # ------------------------------------------------------------------

    @property
    def public_bytes(self) -> bytes:
        """The 32-byte Ed25519 public key for this simulator."""
        return self._public_bytes

    @property
    def robot_did(self) -> str:
        """The ``did:knx:`` identifier this simulator is bound to."""
        return self._robot_did

    # ------------------------------------------------------------------
    # Signing
    # ------------------------------------------------------------------

    def sign_sensor_packet(
        self,
        job_id: str,
        channel: SensorChannel,
        timestamp_ns: int,
        data: bytes,
    ) -> SensorPacket:
        """Atomically increment the per-pair nonce, sign, and return a packet.

        Args:
            job_id: JobID issued by TaskRegistry.
            channel: Sensor channel (enum, not raw string — keeps
                callers from passing arbitrary text).
            timestamp_ns: Capture timestamp; must be non-negative. The
                TEE does not override caller-supplied timestamps; clock
                authority lives one layer up.
            data: Decoded sensor payload (bytes). Empty allowed.

        Returns:
            A fully populated, schema-validated ``SensorPacket``.

        Raises:
            ValueError: If ``timestamp_ns`` is negative.
        """
        if timestamp_ns < 0:
            msg = "timestamp_ns must be non-negative"
            raise ValueError(msg)

        key = (job_id, channel.value)
        nonce = self._monotonic_counter.get(key, 0)
        self._monotonic_counter[key] = nonce + 1

        digest = crypto.canonical_sensor_digest(
            job_id=job_id,
            channel=channel.value,
            timestamp_ns=timestamp_ns,
            nonce=nonce,
            data=data,
        )
        signature = self._sign_canonical_digest(digest)

        return SensorPacket(
            job_id=job_id,
            robot_did=self._robot_did,
            channel=channel,
            timestamp_ns=timestamp_ns,
            nonce=nonce,
            data_b64=base64.b64encode(data).decode("ascii"),
            signature_hex=signature.hex(),
        )

    def _sign_canonical_digest(self, digest: bytes) -> bytes:
        """Single signing site for the private key.

        Kept private and trivial so the audit grep over
        ``_private_bytes`` stays small (``__init__`` for the assign,
        this method for the read).
        """
        return crypto.sign(self._private_bytes, digest)

    # ------------------------------------------------------------------
    # Attestation
    # ------------------------------------------------------------------

    def attest(self) -> dict[str, str]:
        """Return an attestation report.

        The report is a plain ``dict[str, str]`` so it can be JSON-
        serialised by the API layer. It contains exclusively public
        material — never the private key.
        """
        return {
            "robot_did": self._robot_did,
            "public_key_hex": self._public_bytes.hex(),
            "scheme": _SCHEME_TAG,
        }

    # ------------------------------------------------------------------
    # Representations — designed not to leak private bytes
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"TEESimulator(robot_did={self._robot_did!r}, "
            f"public_key={self._public_bytes.hex()})"
        )
