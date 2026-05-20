"""DetVerify Stage 1 — Signature verification.

Wraps :class:`rootid.verifier.RootIDVerifier` so the deterministic
pipeline shares a single signature-checking implementation with Layer A.
A failure here is unrecoverable: the pipeline short-circuits with the
``StageResult.severity == "fail"`` semantics from spec §6.3.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.models import StageResult

if TYPE_CHECKING:
    from core.models import PoPWBundle
    from rootid.verifier import RootIDVerifier

STAGE_NAME = "signature"


def run(
    bundle: PoPWBundle,
    *,
    verifier: RootIDVerifier,
    now_ns: int | None = None,
) -> StageResult:
    """Run Stage 1. Returns ``StageResult`` with severity in {info, fail}."""
    result = verifier.verify_bundle(bundle, now_ns=now_ns)
    if result.valid:
        return StageResult(
            name=STAGE_NAME,
            passed=True,
            detail="all signatures verified",
            severity="info",
        )
    return StageResult(
        name=STAGE_NAME,
        passed=False,
        detail=f"rootid verifier rejected bundle: {result.reason}",
        severity="fail",
    )
