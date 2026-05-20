"""Six-stage deterministic verifier pipeline.

Orchestrates the per-stage modules in :mod:`detverify.stages` and emits
a Konnex-compatible :class:`DetVerifyResult`. Stage 1 (signature) and
any other stage that returns ``severity="fail"`` short-circuits the
pipeline; ``severity="warning"`` continues but penalises the score.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.models import DetVerifyResult
from detverify.score_emitter import compose_score
from detverify.stages import (
    stage1_signature,
    stage2_temporal,
    stage3_crossmodal,
    stage4_replay,
    stage5_anomaly,
    stage6_kinematic,
)

if TYPE_CHECKING:
    from core.models import PoPWBundle, ScoreVector, StageResult
    from detverify.stages.stage6_kinematic import KinematicSpec
    from rootid.verifier import RootIDVerifier


class DetVerifyPipeline:
    """Six-stage deterministic verifier."""

    def __init__(
        self,
        rootid_verifier: RootIDVerifier,
        *,
        kinematic_spec: KinematicSpec | None = None,
    ) -> None:
        self._rootid = rootid_verifier
        self._kinematic_spec = kinematic_spec

    def verify(
        self,
        bundle: PoPWBundle,
        *,
        now_ns: int | None = None,
    ) -> DetVerifyResult:
        """Run all stages and return a ``DetVerifyResult``.

        Stage 1 (signature) short-circuits on failure. Subsequent
        stages also short-circuit on ``severity="fail"`` per spec §6.3
        implementation rules; ``severity="warning"`` continues but
        penalises the score in the emitter.
        """
        results: list[StageResult] = []

        sig = stage1_signature.run(bundle, verifier=self._rootid, now_ns=now_ns)
        results.append(sig)
        if sig.severity == "fail":
            return self._emit(results)

        temporal = stage2_temporal.run(bundle)
        results.append(temporal)
        if temporal.severity == "fail":
            return self._emit(results)

        crossmodal = stage3_crossmodal.run(bundle)
        results.append(crossmodal)
        if crossmodal.severity == "fail":
            return self._emit(results)

        replay = stage4_replay.run(bundle)
        results.append(replay)
        if replay.severity == "fail":
            return self._emit(results)

        anomaly = stage5_anomaly.run(bundle)
        results.append(anomaly)
        # Anomaly is "warning" by design — does not short-circuit.

        kinematic = stage6_kinematic.run(bundle, spec=self._kinematic_spec)
        results.append(kinematic)

        return self._emit(results)

    def _emit(self, results: list[StageResult]) -> DetVerifyResult:
        score: ScoreVector = compose_score(results)
        return DetVerifyResult(
            score=score,
            stage_results=results,
            deterministic_only=True,
        )
