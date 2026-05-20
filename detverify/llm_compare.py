"""Optional GPT-4o reference comparison adapter.

The Konnex AI Verifier published reference is a GPT-4o-mini call over
6 sampled video frames. This module wraps that call so the pipeline
can compare its deterministic verdict with the reference verdict
("layers agree" per the validator-metascore design).

If ``OPENAI_API_KEY`` is not set, ``compare_with_llm`` returns
``None`` rather than raising — the verifier-side fail-secure posture.
The Phase 3 example never depends on this adapter; it is included so
Phase 6 (FastAPI ``/api/verify/with-llm-compare``) can wire it up
without a follow-up patch.

Network calls live behind an explicit boolean flag to keep
unit-test runs hermetic.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.models import PoPWBundle, ScoreVector

log = logging.getLogger(__name__)

_API_KEY_ENV = "OPENAI_API_KEY"


def llm_available() -> bool:
    """Return True iff an ``OPENAI_API_KEY`` is set in the environment."""
    return bool(os.environ.get(_API_KEY_ENV))


def compare_with_llm(
    bundle: PoPWBundle,
    *,
    enabled: bool = False,
) -> ScoreVector | None:
    """Stub for the GPT-4o reference comparison.

    Returns ``None`` unless ``enabled=True`` AND ``OPENAI_API_KEY`` is
    configured. The live implementation lands in Phase 6 alongside
    the FastAPI endpoint that needs it.

    Raising on missing API key would break the fail-secure invariant
    (a missing optional dep should not bring down the deterministic
    pipeline), so we log a warning and return ``None`` instead.
    """
    if not enabled:
        return None
    if not llm_available():
        log.warning(
            "compare_with_llm: %s not set; returning None (no live comparison).",
            _API_KEY_ENV,
        )
        return None
    # Live OpenAI call lives in Phase 6 — placeholder NotImplementedError
    # is the spec-compliant honest behaviour until then.
    msg = "live LLM comparison not yet implemented; arrives in Phase 6"
    raise NotImplementedError(msg)
