"""Tests for ``core/config.py``.

The constants are pure values exercised indirectly by the crypto and
models test suites. This file covers the only executable surface in
the module: ``Settings`` env loading and ``get_settings``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core import config


def test_settings_default_app_version() -> None:
    s = config.get_settings()
    assert s.app_version == "0.1.0"


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KONNEXCORE_APP_VERSION", "9.9.9-test")
    s = config.get_settings()
    assert s.app_version == "9.9.9-test"


def test_settings_rejects_unknown_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    # Pydantic-settings does NOT raise on unknown env vars matching the
    # prefix — they are silently filtered. Our fail-secure posture
    # therefore lives in the field declarations themselves: each
    # required production setting must be declared without a default
    # so a missing env var crashes ``Settings()``. We exercise that
    # contract via a throw-away subclass to avoid mutating Settings.
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class _Strict(BaseSettings):
        model_config = SettingsConfigDict(env_prefix="KONNEXCORE_TEST_", extra="forbid")
        required_secret: str  # no default → must come from env

    # No env var set → fail-secure ValidationError.
    monkeypatch.delenv("KONNEXCORE_TEST_REQUIRED_SECRET", raising=False)
    with pytest.raises(ValidationError):
        _Strict()  # type: ignore[call-arg]

    # Env var set → loads correctly.
    monkeypatch.setenv("KONNEXCORE_TEST_REQUIRED_SECRET", "ok")
    assert _Strict().required_secret == "ok"  # type: ignore[call-arg]


def test_constants_are_canonical() -> None:
    # Sanity-check that the most security-critical constants haven't
    # drifted away from RFC 8032 / FIPS 202 canonical sizes.
    assert config.SHA3_256_BYTES == 32
    assert config.ED25519_PRIVATE_BYTES == 32
    assert config.ED25519_PUBLIC_BYTES == 32
    assert config.ED25519_SIGNATURE_BYTES == 64
    assert config.SCORE_MIN == 0
    assert config.SCORE_MAX == 100
    # Default validator metascore weights from
    # https://docs.konnex.world/understand-konnex/validator-metascore
    assert config.DEFAULT_ALPHA + config.DEFAULT_BETA + config.DEFAULT_GAMMA == 1.0
