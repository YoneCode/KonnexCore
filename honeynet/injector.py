"""Mixes honeypot tasks with organic ones, hides honeypot status from validators.

The injector's only job is the *indistinguishability* property from
spec §6.4: validators receive a stream of :class:`VotingTask` objects
that look identical regardless of whether they are honeypots, while
the oracle retains the ground-truth lookup keyed by ``job_id``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.models import Subnet

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from core.models import HoneypotTask, ScoreVector


@dataclass(frozen=True)
class VotingTask:
    """Public-facing task — what validators see.

    Carries the same shape regardless of honeypot status. The oracle
    receives the *separate* honeypot ground-truth lookup so a validator
    cannot flip behaviour based on packet shape.
    """

    job_id: str
    subnet: Subnet
    prompt: str
    deadline_s: int
    reward_test_knx: float


@dataclass(frozen=True)
class InjectionPlan:
    """Result of mixing organic + honeypot tasks for a simulation run.

    Attributes:
        mixed_tasks: Shuffled tasks given to validators.
        ground_truth_by_job_id: Per-task expected ScoreVector for the
            *honest* simulator (covers both organic and honeypot
            tasks). Validators do not see this map; the oracle and
            the demo's "honest validator" do.
        honeypot_job_ids: Subset of ``mixed_tasks`` job IDs that are
            honeypots. The oracle uses this to apportion votes.
    """

    mixed_tasks: tuple[VotingTask, ...]
    ground_truth_by_job_id: dict[str, ScoreVector]
    honeypot_job_ids: frozenset[str]


def make_organic_voting_task(
    *,
    job_id: str,
    subnet: Subnet = Subnet.ROBOARM,
    prompt: str = "organic task",
    deadline_s: int = 60,
    reward_test_knx: float = 1.0,
) -> VotingTask:
    """Construct a synthetic organic VotingTask."""
    return VotingTask(
        job_id=job_id,
        subnet=subnet,
        prompt=prompt,
        deadline_s=deadline_s,
        reward_test_knx=reward_test_knx,
    )


def _voting_task_from_honeypot(task: HoneypotTask) -> VotingTask:
    return VotingTask(
        job_id=task.job_id,
        subnet=task.subnet,
        prompt=task.prompt,
        deadline_s=task.deadline_s,
        reward_test_knx=task.reward_test_knx,
    )


def inject(
    *,
    organic: Sequence[tuple[VotingTask, ScoreVector]],
    honeypots: Iterable[HoneypotTask],
    seed: int = 0,
) -> InjectionPlan:
    """Mix and shuffle organic + honeypot tasks.

    Args:
        organic: Sequence of ``(VotingTask, expected ScoreVector)``
            tuples — the second element is the *honest* answer the
            simulation uses to model "what a competent validator
            would emit". Validators don't see the ScoreVector.
        honeypots: Iterable of ``HoneypotTask`` instances.
        seed: Seed for the deterministic shuffle.

    Returns:
        An ``InjectionPlan`` whose ``mixed_tasks`` is the public
        validator-facing stream and whose ``ground_truth_by_job_id``
        contains both honeypot and organic ground truths.
    """
    rng = random.Random(seed)

    organic_pairs: list[tuple[VotingTask, ScoreVector]] = list(organic)
    honeypot_list: list[HoneypotTask] = list(honeypots)

    public_tasks: list[VotingTask] = [t for t, _ in organic_pairs]
    public_tasks.extend(_voting_task_from_honeypot(h) for h in honeypot_list)

    truth_map: dict[str, ScoreVector] = {t.job_id: gt for t, gt in organic_pairs}
    for h in honeypot_list:
        truth_map[h.job_id] = h.ground_truth_score

    honeypot_ids = frozenset(h.job_id for h in honeypot_list)

    rng.shuffle(public_tasks)

    return InjectionPlan(
        mixed_tasks=tuple(public_tasks),
        ground_truth_by_job_id=truth_map,
        honeypot_job_ids=honeypot_ids,
    )
