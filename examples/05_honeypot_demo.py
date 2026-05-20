"""Phase 5 honeynet demo — runs 100 organic + 10 honeypot tasks.

Each of the six default-pool validators (honest / lazy / stake-pump /
collusion-A / collusion-B / random) votes on every task in deterministic
order. The :class:`HoneynetOracle` records every vote, then computes
each validator's :math:`H(V_i)`, consensus :math:`C`, penalty :math:`P`,
and the final metascore :math:`S(V_i)`.

Run::

    python examples/05_honeypot_demo.py

Prints a leaderboard sorted by metascore. Exit status is ``0`` iff
the honest validator beats the lazy validator by at least 0.3
metascore points (Phase 5 exit criterion).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

# sys.path bootstrap so this script runs from the project root.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import click  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.table import Table  # noqa: E402

from core.models import Subnet  # noqa: E402
from honeynet.generators.roboarm_gen import (  # noqa: E402
    make_roboarm_honeypot,
    make_roboarm_honeypot_batch,
)
from honeynet.injector import VotingTask, inject  # noqa: E402
from honeynet.oracle import HoneynetOracle  # noqa: E402
from honeynet.validator_pool import VotingContext, default_pool  # noqa: E402

if TYPE_CHECKING:
    from datetime import datetime

    from core.models import ScoreVector, ValidatorVote
    from honeynet.validator_pool import Validator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("05_honeypot_demo")

console = Console()

#: Phase 5 exit-criterion gap threshold.
HONEST_LAZY_GAP_THRESHOLD: float = 0.3


def _ctx(task: VotingTask, truth: ScoreVector, now: datetime) -> VotingContext:
    return VotingContext(task=task, ground_truth_hint=truth, now=now)


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--organic", type=int, default=100, help="Organic task count.")
@click.option("--honeypots", type=int, default=10, help="Honeypot task count.")
@click.option("--seed", type=int, default=42, help="Deterministic seed.")
@click.option(
    "--pure-h",
    is_flag=True,
    default=True,
    help="Use H-only weights (α=0, β=1, γ=0). Default for the demo; spec "
    "defaults α=0.5/β=0.4/γ=0.1 are available without this flag.",
)
def main(organic: int, honeypots: int, seed: int, pure_h: bool) -> None:
    """Run the honeynet demo and print a metascore leaderboard."""
    from datetime import datetime, timezone

    console.rule("[bold]KonnexCore — Honeynet demo[/bold]")
    log.info(
        "running with %d organic, %d honeypot tasks, seed=%d, pure_h=%s",
        organic,
        honeypots,
        seed,
        pure_h,
    )

    oracle = (
        HoneynetOracle(alpha=0.0, beta=1.0, gamma=0.0)
        if pure_h
        else HoneynetOracle()  # spec defaults
    )

    validators: list[Validator] = default_pool(seed=seed)

    # Organic tasks share the honeypot generator's truth distribution
    # so the simulation has a realistic "ground truth" for the
    # honest-validator hint to consume.
    organic_pairs: list[tuple[VotingTask, ScoreVector]] = []
    for i in range(organic):
        hp = make_roboarm_honeypot(seed=999, idx=i)
        organic_pairs.append(
            (
                VotingTask(
                    job_id=f"organic-{i}",
                    subnet=Subnet.ROBOARM,
                    prompt=f"organic task #{i}",
                    deadline_s=60,
                    reward_test_knx=1.0,
                ),
                hp.ground_truth_score,
            ),
        )

    honeypot_tasks = make_roboarm_honeypot_batch(seed=seed, n=honeypots)
    for hp in honeypot_tasks:
        oracle.register_honeypot(hp)

    plan = inject(organic=organic_pairs, honeypots=honeypot_tasks, seed=seed)

    now = datetime.now(tz=timezone.utc)
    for task in plan.mixed_tasks:
        truth = plan.ground_truth_by_job_id[task.job_id]
        # Validators vote in pool order; lazy is last so it sees all
        # peer votes (per default_pool's design).
        votes_so_far: list[ValidatorVote] = []
        for v in validators:
            vote = v.vote(_ctx(task, truth, now), peer_votes=list(votes_so_far))
            votes_so_far.append(vote)
            oracle.submit_vote(vote)

    # Collect metascores.
    rows = [(v.did, oracle.compute_metascore(v.did)) for v in validators]
    rows.sort(key=lambda row: row[1].metascore, reverse=True)

    table = Table(title="Validator metascore leaderboard", show_header=True, header_style="bold")
    table.add_column("Rank", justify="right")
    table.add_column("DID")
    table.add_column("C(V)", justify="right")
    table.add_column("H(V)", justify="right")
    table.add_column("P(V)", justify="right")
    table.add_column("S(V)", justify="right")
    table.add_column("# honeypots", justify="right")
    for rank, (did, ms) in enumerate(rows, start=1):
        table.add_row(
            str(rank),
            did.removeprefix("did:knx:testnet:"),
            f"{ms.consensus_term:.3f}",
            f"{ms.honeypot_accuracy:.3f}",
            f"{ms.penalty_score:.3f}",
            f"{ms.metascore:.3f}",
            str(ms.sample_count),
        )
    console.print(table)

    honest = next(ms for did, ms in rows if did.endswith("val-honest"))
    lazy = next(ms for did, ms in rows if did.endswith("val-lazy"))
    gap = honest.metascore - lazy.metascore

    if gap >= HONEST_LAZY_GAP_THRESHOLD:
        console.print(
            Panel.fit(
                f"[bold green]EXIT CRITERION MET[/bold green]  "
                f"honest={honest.metascore:.3f} − lazy={lazy.metascore:.3f} "
                f"= {gap:.3f} ≥ {HONEST_LAZY_GAP_THRESHOLD}",
                title="Phase 5",
            ),
        )
        sys.exit(0)
    else:  # pragma: no cover
        console.print(
            Panel.fit(
                f"[bold red]EXIT CRITERION FAILED[/bold red]  "
                f"gap={gap:.3f} < {HONEST_LAZY_GAP_THRESHOLD}",
                title="Phase 5",
            ),
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
