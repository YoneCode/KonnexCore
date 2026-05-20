"""Five simulated validator archetypes for the honeypot demo.

Each archetype implements the :class:`Validator` protocol and emits
``ValidatorVote``s for tasks. The honeypot oracle later compares the
votes against ground-truth answers to compute per-validator
:math:`H(V_i)`; the network as a whole computes
:math:`C(W_i, \\bar W)` consensus alignment from the same vote stream.

Archetypes (per spec §6.4)
--------------------------

* ``HonestValidator`` — runs the full deterministic verifier (modelled
  here as: read the task's ground-truth proxy with mild noise).
* ``LazyValidator`` — copies the per-axis median of the peer votes
  it has already observed.
* ``StakePumpValidator`` — always votes high-and-success regardless
  of the input.
* ``CollusionValidator`` — two instances share a deterministic seed
  so they emit byte-identical votes for every task.
* ``RandomValidator`` — uniform-random scores per axis.

A real Konnex validator stack would replace ``HonestValidator``'s
``vote()`` with the full DetVerify pipeline; this module's purpose is
to expose the metascore separation, so the honest archetype simply
trusts the supplied ground-truth proxy.
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Protocol

from core.models import ScoreVector, ValidatorVote

if TYPE_CHECKING:
    from honeynet.injector import VotingTask


_AXES = (
    "accuracy",
    "speed",
    "safety",
    "optimal_track",
    "energy_efficiency",
    "trajectory_stability",
)


@dataclass(frozen=True)
class VotingContext:
    """Per-task voting context shared across archetypes.

    ``ground_truth_hint`` is the *honest* proxy a real validator would
    independently derive by running DetVerify. The honeypot oracle
    learns the same value through ``HoneypotTask.ground_truth_score``.
    For organic tasks the ``ground_truth_hint`` is the network's
    *expected* answer — the simulation uses it as a stand-in for what
    a competent verifier would produce.
    """

    task: VotingTask
    ground_truth_hint: ScoreVector
    now: datetime


class Validator(Protocol):
    """Interface every archetype implements."""

    @property
    def did(self) -> str: ...

    def vote(
        self,
        ctx: VotingContext,
        peer_votes: list[ValidatorVote],
    ) -> ValidatorVote: ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _axes_dict(score: ScoreVector) -> dict[str, int]:
    return {axis: getattr(score, axis) for axis in _AXES}


def _score_from_axes(
    axes: dict[str, int],
    *,
    verdict: str = "success",
    reasoning: str = "",
) -> ScoreVector:
    final_pct = sum(axes.values()) // len(_AXES)
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


def _clamp(value: int) -> int:
    return max(0, min(100, value))


# ---------------------------------------------------------------------------
# HonestValidator
# ---------------------------------------------------------------------------


class HonestValidator:
    """Mirrors the supplied ground truth, with mild deterministic noise."""

    def __init__(self, did: str, *, seed: int = 0, noise: int = 2) -> None:
        self._did = did
        self._rng = random.Random(seed)
        self._noise = noise

    @property
    def did(self) -> str:
        return self._did

    def vote(
        self,
        ctx: VotingContext,
        peer_votes: list[ValidatorVote],
    ) -> ValidatorVote:
        truth = _axes_dict(ctx.ground_truth_hint)
        jittered = {
            axis: _clamp(value + self._rng.randint(-self._noise, self._noise))
            for axis, value in truth.items()
        }
        score = _score_from_axes(
            jittered,
            verdict=ctx.ground_truth_hint.verdict,
            reasoning="honest vote with bounded noise",
        )
        return ValidatorVote(
            validator_did=self._did,
            job_id=ctx.task.job_id,
            score=score,
            submitted_at=ctx.now,
        )


# ---------------------------------------------------------------------------
# LazyValidator
# ---------------------------------------------------------------------------


class LazyValidator:
    """Copies the per-axis median of peer votes seen so far.

    If no peer has voted yet, falls back to a flat ``50`` across all
    axes — the worst kind of "I don't know" output a lazy node can
    produce.
    """

    def __init__(self, did: str) -> None:
        self._did = did

    @property
    def did(self) -> str:
        return self._did

    def vote(
        self,
        ctx: VotingContext,
        peer_votes: list[ValidatorVote],
    ) -> ValidatorVote:
        if not peer_votes:
            axes = dict.fromkeys(_AXES, 50)
        else:
            axes = {
                axis: int(round(statistics.median(getattr(v.score, axis) for v in peer_votes)))
                for axis in _AXES
            }
        score = _score_from_axes(
            axes,
            verdict="success",
            reasoning="lazy: per-axis median of peer votes",
        )
        return ValidatorVote(
            validator_did=self._did,
            job_id=ctx.task.job_id,
            score=score,
            submitted_at=ctx.now,
        )


# ---------------------------------------------------------------------------
# StakePumpValidator
# ---------------------------------------------------------------------------


class StakePumpValidator:
    """Always votes a flat high-success — never does the work."""

    def __init__(self, did: str, *, score_value: int = 95) -> None:
        self._did = did
        self._value = score_value

    @property
    def did(self) -> str:
        return self._did

    def vote(
        self,
        ctx: VotingContext,
        peer_votes: list[ValidatorVote],
    ) -> ValidatorVote:
        score = ScoreVector(
            accuracy=self._value,
            speed=self._value,
            safety=self._value,
            optimal_track=self._value,
            energy_efficiency=self._value,
            trajectory_stability=self._value,
            final_pct=self._value,
            verdict="success",
            reasoning="stake-pump: always success",
        )
        return ValidatorVote(
            validator_did=self._did,
            job_id=ctx.task.job_id,
            score=score,
            submitted_at=ctx.now,
        )


# ---------------------------------------------------------------------------
# CollusionValidator
# ---------------------------------------------------------------------------


class CollusionValidator:
    """Two instances sharing the same seed produce identical votes.

    The collusion archetype is constructed via :func:`make_collusion_pair`
    to enforce that two validators share the deterministic vote stream.
    """

    def __init__(self, did: str, *, shared_seed: int) -> None:
        self._did = did
        self._rng = random.Random(shared_seed)

    @property
    def did(self) -> str:
        return self._did

    def vote(
        self,
        ctx: VotingContext,
        peer_votes: list[ValidatorVote],
    ) -> ValidatorVote:
        # Drive the RNG by job_id so two CollusionValidator instances
        # initialised with the same shared_seed produce identical
        # votes per job, regardless of vote ordering.
        local_rng = random.Random(f"{self._rng.random()}:{ctx.task.job_id}")
        axes = {axis: local_rng.randint(60, 80) for axis in _AXES}
        score = _score_from_axes(
            axes,
            verdict="success",
            reasoning="collusion: shared-seed deterministic vote",
        )
        return ValidatorVote(
            validator_did=self._did,
            job_id=ctx.task.job_id,
            score=score,
            submitted_at=ctx.now,
        )


def make_collusion_pair(
    did_a: str,
    did_b: str,
    *,
    shared_seed: int,
) -> tuple[CollusionValidator, CollusionValidator]:
    """Construct two ``CollusionValidator``s that agree byte-for-byte."""
    return (
        CollusionValidator(did_a, shared_seed=shared_seed),
        CollusionValidator(did_b, shared_seed=shared_seed),
    )


# ---------------------------------------------------------------------------
# RandomValidator
# ---------------------------------------------------------------------------


class RandomValidator:
    """Uniform-random per-axis scores; does no work at all."""

    def __init__(self, did: str, *, seed: int = 0) -> None:
        self._did = did
        self._rng = random.Random(seed)

    @property
    def did(self) -> str:
        return self._did

    def vote(
        self,
        ctx: VotingContext,
        peer_votes: list[ValidatorVote],
    ) -> ValidatorVote:
        axes = {axis: self._rng.randint(0, 100) for axis in _AXES}
        verdict_choice = self._rng.choice(("success", "failure", "inconclusive"))
        score = _score_from_axes(
            axes,
            verdict=verdict_choice,
            reasoning="random vote",
        )
        return ValidatorVote(
            validator_did=self._did,
            job_id=ctx.task.job_id,
            score=score,
            submitted_at=ctx.now,
        )


# ---------------------------------------------------------------------------
# Pool factory
# ---------------------------------------------------------------------------


def default_pool(*, seed: int = 0) -> list[Validator]:
    """Return the canonical 6-validator pool with lazy voting *last*.

    Voting order matters for ``LazyValidator``: it copies the per-axis
    median of the peer votes it has *already observed*. Putting lazy
    last gives it the full peer-vote sample so the simulation tests
    its actual median-of-peers behaviour rather than degenerating into
    "lazy copies the first peer to vote".
    """
    collusion_a, collusion_b = make_collusion_pair(
        "did:knx:testnet:val-collusion-a",
        "did:knx:testnet:val-collusion-b",
        shared_seed=seed + 100,
    )
    return [
        HonestValidator("did:knx:testnet:val-honest", seed=seed + 1),
        StakePumpValidator("did:knx:testnet:val-stakepump"),
        collusion_a,
        collusion_b,
        RandomValidator("did:knx:testnet:val-random", seed=seed + 2),
        LazyValidator("did:knx:testnet:val-lazy"),
    ]


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)
