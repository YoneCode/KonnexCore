"""Validator metascore math.

Implements the Konnex validator metascore formula
``S(V_i) = α·C(W_i, W̄) − γ·P_i + β·H(V_i)`` with a rearranged sign on
the consensus and penalty terms (subtraction of the penalty stays
faithful to the published formula).

Source: https://docs.konnex.world/understand-konnex/validator-metascore

Score-vector comparison
-----------------------
Spec text suggests cosine similarity. Cosine collapses to ~1.0 for any
two non-negative vectors that are roughly aligned in shape, which
makes it useless at separating "all-90" stake-pump votes from
honest ones (both align with a typical positive ground-truth
vector). We therefore use a normalised L1-based similarity:

    sim(a, b) = max(0, 1 − Σ|a_i − b_i| / (n · 100))

over the six per-axis fields of :class:`core.models.ScoreVector`. The
function returns ``1.0`` for identical vectors and ``0.0`` for two
vectors at maximal disagreement (one all-zero, one all-100). Phase 8
hardening can swap in cosine if Konnex confirms it as the protocol
metric; the call sites depend only on the abstract similarity contract.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config import (
    DEFAULT_ALPHA,
    DEFAULT_BETA,
    DEFAULT_GAMMA,
    SCORE_MAX,
)

if TYPE_CHECKING:
    from core.models import ScoreVector

_SCORE_AXES = (
    "accuracy",
    "speed",
    "safety",
    "optimal_track",
    "energy_efficiency",
    "trajectory_stability",
)


def _axis_vector(score: ScoreVector) -> tuple[int, ...]:
    """Extract the six per-axis values as a tuple."""
    return tuple(getattr(score, axis) for axis in _SCORE_AXES)


def vector_similarity(a: ScoreVector, b: ScoreVector) -> float:
    """Return a normalised similarity in ``[0, 1]`` between two ScoreVectors.

    Uses a normalised L1 distance over the six per-axis fields:

        sim = max(0, 1 − Σ|a_i − b_i| / (n · SCORE_MAX))

    Args:
        a, b: Score vectors with per-axis values in ``[0, SCORE_MAX]``.

    Returns:
        ``1.0`` for identical vectors, ``0.0`` for maximal disagreement.
    """
    axes_a = _axis_vector(a)
    axes_b = _axis_vector(b)
    total_diff = sum(abs(x - y) for x, y in zip(axes_a, axes_b, strict=True))
    max_diff = len(_SCORE_AXES) * SCORE_MAX
    sim = 1.0 - (total_diff / max_diff)
    return max(0.0, sim)


def compute_metascore(  # noqa: PLR0913 — α/β/γ + 3 components are spec-mandated
    *,
    consensus: float,
    honeypot_accuracy: float,
    penalty: float,
    alpha: float = DEFAULT_ALPHA,
    beta: float = DEFAULT_BETA,
    gamma: float = DEFAULT_GAMMA,
) -> float:
    """Compute ``S(V_i) = α·C + β·H − γ·P`` and clip to ``[0, 1]``.

    All inputs are expected in ``[0, 1]``. Negative or super-unit
    values pass through but the result is clipped.
    """
    raw = alpha * consensus + beta * honeypot_accuracy - gamma * penalty
    return max(0.0, min(1.0, raw))
