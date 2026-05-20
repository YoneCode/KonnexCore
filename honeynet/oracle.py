"""Honeypot comparison oracle.

The oracle holds a registry of honeypot tasks (each with a hidden
ground-truth :class:`ScoreVector`), accepts validator votes via
:meth:`HoneynetOracle.submit_vote`, and exposes per-validator
honeypot accuracy :math:`H(V_i)` plus the full
:class:`ValidatorMetascore` :math:`S(V_i)` from spec §6.4.

Consensus :math:`C(W_i, \\bar W)` is computed against the per-job
*median* ScoreVector across all observed validators — a robust proxy
for the network's "truth" without requiring a Konnex-side reference.
"""

from __future__ import annotations

import statistics
from typing import TYPE_CHECKING

from core.config import DEFAULT_ALPHA, DEFAULT_BETA, DEFAULT_GAMMA
from core.models import ScoreVector, ValidatorMetascore
from honeynet.metascore import compute_metascore, vector_similarity

if TYPE_CHECKING:
    from core.models import HoneypotTask, ValidatorVote

_AXES = (
    "accuracy",
    "speed",
    "safety",
    "optimal_track",
    "energy_efficiency",
    "trajectory_stability",
)

#: Need at least this many votes on a job before consensus is meaningful.
_MIN_PEERS_FOR_CONSENSUS: int = 2


class HoneynetOracleError(RuntimeError):
    """Operational error raised by the oracle."""


class HoneynetOracle:
    """Per-validator metascore tracker."""

    def __init__(
        self,
        *,
        alpha: float = DEFAULT_ALPHA,
        beta: float = DEFAULT_BETA,
        gamma: float = DEFAULT_GAMMA,
    ) -> None:
        if alpha < 0 or beta < 0 or gamma < 0:
            msg = "metascore weights must be non-negative"
            raise ValueError(msg)
        self._alpha = alpha
        self._beta = beta
        self._gamma = gamma
        self._honeypots: dict[str, HoneypotTask] = {}
        # validator_did → list of (job_id, ScoreVector)
        self._votes_by_validator: dict[str, list[tuple[str, ScoreVector]]] = {}
        # job_id → list of ScoreVector (used for consensus median)
        self._votes_by_job: dict[str, list[ScoreVector]] = {}

    # ------------------------------------------------------------------
    # Registration + ingestion
    # ------------------------------------------------------------------

    def register_honeypot(self, task: HoneypotTask) -> None:
        """Register a honeypot's hidden ground truth, keyed by ``job_id``.

        Raises:
            HoneynetOracleError: If ``task.job_id`` is already registered
                under a different ground truth.
        """
        existing = self._honeypots.get(task.job_id)
        if existing is not None and existing.ground_truth_score != task.ground_truth_score:
            msg = f"honeypot {task.job_id!r} already registered with a " "different ground truth"
            raise HoneynetOracleError(msg)
        self._honeypots[task.job_id] = task

    def submit_vote(self, vote: ValidatorVote) -> None:
        """Record a validator vote.

        Votes for both honeypot and organic jobs flow through here;
        the oracle distinguishes them via ``register_honeypot`` lookups.
        """
        self._votes_by_validator.setdefault(vote.validator_did, []).append(
            (vote.job_id, vote.score),
        )
        self._votes_by_job.setdefault(vote.job_id, []).append(vote.score)

    # ------------------------------------------------------------------
    # Per-validator score components
    # ------------------------------------------------------------------

    def honeypot_accuracy(self, validator_did: str) -> tuple[float, int]:
        """Return ``(H(V_i), honeypot_sample_count)`` for ``validator_did``.

        ``H`` is the mean similarity across the honeypot votes the
        validator submitted. If the validator never voted on any
        registered honeypot, returns ``(0.0, 0)``.
        """
        votes = self._votes_by_validator.get(validator_did, [])
        sims: list[float] = []
        for job_id, score in votes:
            honeypot = self._honeypots.get(job_id)
            if honeypot is None:
                continue
            sims.append(vector_similarity(score, honeypot.ground_truth_score))
        if not sims:
            return 0.0, 0
        return sum(sims) / len(sims), len(sims)

    def consensus_alignment(self, validator_did: str) -> float:
        """Return ``C(W_i, W̄)`` — mean similarity to the per-job median.

        For every job the validator voted on, compute the per-axis
        median across the network's observed votes for that job, then
        compare the validator's vote to the median. Mean of those
        similarities is the consensus score.
        """
        votes = self._votes_by_validator.get(validator_did, [])
        if not votes:
            return 0.0
        sims: list[float] = []
        for job_id, score in votes:
            peers = self._votes_by_job.get(job_id, [])
            if len(peers) < _MIN_PEERS_FOR_CONSENSUS:
                continue
            median = self._median_score(peers)
            sims.append(vector_similarity(score, median))
        if not sims:
            return 0.0
        return sum(sims) / len(sims)

    @staticmethod
    def _median_score(votes: list[ScoreVector]) -> ScoreVector:
        """Per-axis median across ``votes``. Verdict copied from majority."""
        axes = {
            axis: int(round(statistics.median(getattr(v, axis) for v in votes))) for axis in _AXES
        }
        verdicts = [v.verdict for v in votes]
        # Most common verdict; ties resolved by Counter ordering.
        majority_verdict = max(set(verdicts), key=verdicts.count)
        final_pct = sum(axes.values()) // len(_AXES)
        return ScoreVector(
            accuracy=axes["accuracy"],
            speed=axes["speed"],
            safety=axes["safety"],
            optimal_track=axes["optimal_track"],
            energy_efficiency=axes["energy_efficiency"],
            trajectory_stability=axes["trajectory_stability"],
            final_pct=final_pct,
            verdict=majority_verdict,
            reasoning="network median",
        )

    def penalty(self, validator_did: str) -> float:
        """Return ``P_i`` for ``validator_did``.

        Phase 5 has no operational-penalty surface beyond
        non-participation: a validator that submitted zero votes
        gets ``P = 1.0``; otherwise ``P = 0.0``. Phase 8 hardening
        wires real penalties (timeouts, abstentions, slashing).
        """
        if not self._votes_by_validator.get(validator_did):
            return 1.0
        return 0.0

    # ------------------------------------------------------------------
    # Final metascore
    # ------------------------------------------------------------------

    def compute_metascore(self, validator_did: str) -> ValidatorMetascore:
        """Compose ``S(V_i) = α·C + β·H − γ·P`` for ``validator_did``."""
        consensus = self.consensus_alignment(validator_did)
        honeypot_h, sample_count = self.honeypot_accuracy(validator_did)
        penalty_score = self.penalty(validator_did)

        metascore = compute_metascore(
            consensus=consensus,
            honeypot_accuracy=honeypot_h,
            penalty=penalty_score,
            alpha=self._alpha,
            beta=self._beta,
            gamma=self._gamma,
        )

        return ValidatorMetascore(
            validator_did=validator_did,
            consensus_term=consensus,
            honeypot_accuracy=honeypot_h,
            penalty_score=penalty_score,
            alpha=self._alpha,
            beta=self._beta,
            gamma=self._gamma,
            metascore=metascore,
            sample_count=sample_count,
        )

    def known_validators(self) -> list[str]:
        """List validator DIDs that have submitted at least one vote."""
        return list(self._votes_by_validator.keys())
