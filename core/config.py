"""Project-wide constants and runtime settings.

This module is the single source of truth for magic numbers per the
anti-slop rule in design spec Section 4. It also exposes a ``Settings``
class loaded from environment variables via pydantic-settings.

Settings are fail-secure: missing required variables raise
``pydantic.ValidationError`` at import time rather than silently
defaulting to insecure values (per the ``insecure-defaults`` skill).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Cryptographic primitives (sizes in bytes)
# ---------------------------------------------------------------------------

#: SHA-3-256 digest size in bytes. Konnex protocol uses SHA-3 exclusively
#: (https://docs.konnex.world/understand-konnex/protocol-architecture).
SHA3_256_BYTES: int = 32

#: Ed25519 private key size in bytes (RFC 8032 §5.1.5).
ED25519_PRIVATE_BYTES: int = 32

#: Ed25519 public key size in bytes (RFC 8032 §5.1.5).
ED25519_PUBLIC_BYTES: int = 32

#: Ed25519 signature size in bytes (RFC 8032 §5.1.6).
ED25519_SIGNATURE_BYTES: int = 64

# ---------------------------------------------------------------------------
# Schema-level invariants
# ---------------------------------------------------------------------------

#: Minimum value for any ScoreVector field per Konnex AI Verifier schema.
SCORE_MIN: int = 0

#: Maximum value for any ScoreVector field per Konnex AI Verifier schema.
SCORE_MAX: int = 100

#: Default validator metascore weights (S(V_i) = α·C + β·H − γ·P).
#: Source: https://docs.konnex.world/understand-konnex/validator-metascore
DEFAULT_ALPHA: float = 0.5
DEFAULT_BETA: float = 0.4
DEFAULT_GAMMA: float = 0.1


class Settings(BaseSettings):
    """Runtime settings loaded from environment.

    All future env-driven settings (LLM API key, VPS host, etc.) declare
    themselves here. At Phase 0 the only field is ``app_version``, which
    has a non-secret default and is safe to expose in ``/api/health``.
    """

    model_config = SettingsConfigDict(
        env_prefix="KONNEXCORE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
    )

    app_version: str = "0.1.0"


def get_settings() -> Settings:
    """Construct a fresh ``Settings`` instance.

    Returns:
        A ``Settings`` populated from environment variables and ``.env``.

    Raises:
        pydantic.ValidationError: If a required env var is missing or
            malformed. (No required vars at Phase 0; raised by future
            phases that add fail-secure secrets.)
    """
    return Settings()
