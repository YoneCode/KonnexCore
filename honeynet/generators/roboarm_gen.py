"""Deterministic honeypot generator for the roboarm subnet.

A real Konnex honeynet would render full PyBullet scenes whose ground
truth is computed by simulating the policy. Phase 5 ships a synthetic
generator: deterministic per-index ScoreVectors covering the success /
failure / inconclusive verdict triple, so the metascore demo has a
realistic mix of "hard to fake" answers.

Each honeypot's ``ground_truth_hash`` commits to its
``ground_truth_score`` via ``core.crypto.sha3_256`` of the JSON-encoded
score, so a Phase 6 onchain anchor can post the commitment alongside
the public task. Validators do not see this commitment until after
they vote.
"""

from __future__ import annotations

import random

from core import crypto
from core.models import HoneypotTask, ScoreVector, Subnet


def _rand_score(rng: random.Random, *, low: int, high: int) -> int:
    return rng.randint(low, high)


def _ground_truth_for(rng: random.Random, idx: int) -> ScoreVector:
    """Build a deterministic, varied ScoreVector for honeypot ``idx``.

    Rotation (period 5) — failure archetypes are 60% of the mix
    because they are the most discriminating: a lazy validator that
    copies the network median (which sits in the 70-95 band when
    the pool is adversarial-heavy) is most clearly wrong on a
    "failure" honeypot whose ground truth is in the 5-30 band.

    * idx % 5 == 0 → success (high scores, mild noise)
    * idx % 5 == 1, 2, 4 → failure (low scores, mild noise)
    * idx % 5 == 3 → inconclusive (mid scores, mild noise)
    """
    bucket = idx % 5
    if bucket == 0:
        # success — high values
        axes = {
            "accuracy": _rand_score(rng, low=85, high=95),
            "speed": _rand_score(rng, low=80, high=95),
            "safety": _rand_score(rng, low=90, high=100),
            "optimal_track": _rand_score(rng, low=80, high=95),
            "energy_efficiency": _rand_score(rng, low=80, high=95),
            "trajectory_stability": _rand_score(rng, low=85, high=95),
        }
        verdict: str = "success"
    elif bucket in (1, 2, 4):
        # failure — low values
        axes = {
            "accuracy": _rand_score(rng, low=5, high=20),
            "speed": _rand_score(rng, low=10, high=30),
            "safety": _rand_score(rng, low=30, high=60),
            "optimal_track": _rand_score(rng, low=5, high=20),
            "energy_efficiency": _rand_score(rng, low=20, high=40),
            "trajectory_stability": _rand_score(rng, low=10, high=30),
        }
        verdict = "failure"
    else:
        # inconclusive — mid values
        axes = {
            "accuracy": _rand_score(rng, low=40, high=60),
            "speed": _rand_score(rng, low=40, high=60),
            "safety": _rand_score(rng, low=50, high=70),
            "optimal_track": _rand_score(rng, low=40, high=60),
            "energy_efficiency": _rand_score(rng, low=40, high=60),
            "trajectory_stability": _rand_score(rng, low=40, high=60),
        }
        verdict = "inconclusive"

    final_pct = sum(axes.values()) // len(axes)
    return ScoreVector(
        accuracy=axes["accuracy"],
        speed=axes["speed"],
        safety=axes["safety"],
        optimal_track=axes["optimal_track"],
        energy_efficiency=axes["energy_efficiency"],
        trajectory_stability=axes["trajectory_stability"],
        final_pct=final_pct,
        verdict=verdict,  # type: ignore[arg-type]
        reasoning=f"roboarm honeypot ground truth ({verdict})",
    )


def make_roboarm_honeypot(
    *,
    seed: int,
    idx: int,
    deadline_s: int = 60,
    reward_test_knx: float = 1.0,
) -> HoneypotTask:
    """Construct one deterministic roboarm honeypot.

    Args:
        seed: Top-level seed shared with sibling honeypots.
        idx: 0-based index within the batch — drives the
            success/failure/inconclusive rotation.
        deadline_s: Validation deadline in seconds (mirrors organic).
        reward_test_knx: Test-KNX reward (mirrors organic).

    Returns:
        A ``HoneypotTask`` with a stable ``job_id`` derived from the
        seed and index, plus a SHA-3 ``ground_truth_hash`` commitment.
    """
    rng = random.Random(f"roboarm:{seed}:{idx}")
    job_id = crypto.sha3_256(f"roboarm:hp:{seed}:{idx}".encode()).hex()
    score = _ground_truth_for(rng, idx)
    score_bytes = score.model_dump_json().encode()
    ground_truth_hash = crypto.sha3_256(score_bytes).hex()
    return HoneypotTask(
        job_id=job_id,
        subnet=Subnet.ROBOARM,
        prompt=f"roboarm honeypot #{idx}: {score.verdict} archetype",
        deadline_s=deadline_s,
        reward_test_knx=reward_test_knx,
        ground_truth_score=score,
        ground_truth_hash=ground_truth_hash,
    )


def make_roboarm_honeypot_batch(*, seed: int, n: int) -> list[HoneypotTask]:
    """Construct ``n`` deterministic roboarm honeypots."""
    return [make_roboarm_honeypot(seed=seed, idx=i) for i in range(n)]


def verify_ground_truth_commitment(task: HoneypotTask) -> bool:
    """Re-derive the SHA-3 commitment from the score and compare.

    Useful for the Phase 6 onchain-anchor flow: the commitment posted
    onchain must be reproducible from the revealed score.
    """
    score_bytes = task.ground_truth_score.model_dump_json().encode()
    expected = crypto.sha3_256(score_bytes).hex()
    return task.ground_truth_hash == expected


# Sanity check that the module-level encoding contract holds.
# (Cheap, runs at import; would surface a Pydantic schema drift quickly.)
_sample = make_roboarm_honeypot(seed=0xC0DE, idx=0)
if not verify_ground_truth_commitment(_sample):  # pragma: no cover — guard
    msg = "roboarm honeypot ground-truth commitment self-check failed at import"
    raise RuntimeError(msg)
del _sample

# Re-export for example imports.
__all__ = [
    "make_roboarm_honeypot",
    "make_roboarm_honeypot_batch",
    "verify_ground_truth_commitment",
]
