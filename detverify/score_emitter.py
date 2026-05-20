"""Compose a Konnex-compatible :class:`ScoreVector` from stage results.

Stage outcomes are mapped onto the six per-axis Konnex scores
(``accuracy``, ``speed``, ``safety``, ``optimal_track``,
``energy_efficiency``, ``trajectory_stability``). The mapping below
is deliberately opinionated — a Phase 8 hardening pass tunes weights
against real validator workloads.

Score-derivation rules
----------------------

* If signature (Stage 1) failed → all axes drop to 0,
  ``verdict='failure'``.
* Otherwise each axis starts at 100 and is decremented by per-stage
  penalties:
  * temporal failure  → -40 trajectory_stability
  * crossmodal fail   → -40 safety, -20 accuracy
  * replay fail       → -40 safety, -20 accuracy
  * anomaly warning   → -15 safety
  * kinematic fail    → -50 safety, -20 energy_efficiency
* ``final_pct`` is the integer mean of the six axes.
* ``verdict``:
  * ``final_pct >= 80`` → ``"success"``
  * ``final_pct <= 30`` → ``"failure"``
  * otherwise           → ``"inconclusive"``
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.models import ScoreVector

if TYPE_CHECKING:
    from core.models import StageResult

#: Axis penalties for each (stage, severity) tuple.
#: Each entry maps to (axis_name, points-to-subtract).
_PENALTIES: dict[tuple[str, str], tuple[tuple[str, int], ...]] = {
    ("temporal", "fail"): (("trajectory_stability", 40),),
    ("crossmodal", "fail"): (("safety", 40), ("accuracy", 20)),
    ("replay", "fail"): (("safety", 40), ("accuracy", 20)),
    ("anomaly", "warning"): (("safety", 15),),
    ("kinematic", "fail"): (("safety", 50), ("energy_efficiency", 20)),
}

_AXES = (
    "accuracy",
    "speed",
    "safety",
    "optimal_track",
    "energy_efficiency",
    "trajectory_stability",
)

#: Final-percentage thresholds for the Konnex verdict triple.
#: Phase 3 exit criterion (spec §9): clean ≥ 80, adversarial ≤ 30.
VERDICT_SUCCESS_THRESHOLD: int = 80
VERDICT_FAILURE_THRESHOLD: int = 30

#: Hard ceiling applied when any stage returns ``severity="fail"``.
#: Without it the per-axis penalties wouldn't push final_pct below
#: ``VERDICT_FAILURE_THRESHOLD`` for every individual stage failure;
#: the cap guarantees Phase 3 exit-criterion compliance for any
#: adversarial bundle that trips a fail-severity stage.
FAILURE_HARD_CAP: int = 25


def compose_score(stage_results: list[StageResult]) -> ScoreVector:
    """Map stage outcomes to a Konnex ``ScoreVector``."""
    # Signature failure collapses everything to 0 / failure.
    sig_fail = any(r.name == "signature" and not r.passed for r in stage_results)
    if sig_fail:
        sig_detail = next(
            (r.detail for r in stage_results if r.name == "signature"),
            "signature stage failed",
        )
        return ScoreVector(
            accuracy=0,
            speed=0,
            safety=0,
            optimal_track=0,
            energy_efficiency=0,
            trajectory_stability=0,
            final_pct=0,
            verdict="failure",
            reasoning=f"signature stage failed: {sig_detail}",
        )

    axes: dict[str, int] = dict.fromkeys(_AXES, 100)
    notes: list[str] = []
    for result in stage_results:
        key = (result.name, result.severity)
        penalties = _PENALTIES.get(key, ())
        if penalties:
            for axis, delta in penalties:
                axes[axis] = max(0, axes[axis] - delta)
            notes.append(f"{result.name}:{result.severity} → {result.detail}")

    final_pct = sum(axes.values()) // len(axes)

    # If any (non-signature) stage failed, cap the score so the
    # Konnex verdict reliably reaches "failure" — single signature
    # successes paired with one downstream fail would otherwise
    # average to 60-something and fall in the "inconclusive" band.
    has_fail = any(r.severity == "fail" and r.name != "signature" for r in stage_results)
    if has_fail:
        final_pct = min(final_pct, FAILURE_HARD_CAP)

    if final_pct >= VERDICT_SUCCESS_THRESHOLD:
        verdict: str = "success"
    elif final_pct <= VERDICT_FAILURE_THRESHOLD:
        verdict = "failure"
    else:
        verdict = "inconclusive"

    reasoning = "; ".join(notes) if notes else "all deterministic stages passed"

    return ScoreVector(
        accuracy=axes["accuracy"],
        speed=axes["speed"],
        safety=axes["safety"],
        optimal_track=axes["optimal_track"],
        energy_efficiency=axes["energy_efficiency"],
        trajectory_stability=axes["trajectory_stability"],
        final_pct=final_pct,
        verdict=verdict,  # type: ignore[arg-type]
        reasoning=reasoning,
    )
