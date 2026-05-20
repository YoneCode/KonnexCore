"""Phase 4 attack-lab demo.

Run::

    python examples/04_attack_lab.py

For each of the five adversarial generators in
:mod:`core.attack_lab`, this script:

1. Builds the adversarial bundle.
2. Runs it through ``DetVerifyPipeline``.
3. Renders the outcome — caught stage, severity, ``final_pct``, and
   the per-stage failure reason — into a single comparison table.

Exit code is ``0`` iff every attack was caught at its declared
expected stage (Phase 4 exit criterion).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

# sys.path bootstrap so the script runs without PYTHONPATH.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.table import Table  # noqa: E402

from core.attack_lab import ATTACK_GENERATORS, AttackOutcome  # noqa: E402
from detverify.pipeline import DetVerifyPipeline  # noqa: E402
from detverify.score_emitter import VERDICT_FAILURE_THRESHOLD  # noqa: E402
from rootid.verifier import RootIDVerifier  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Callable

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("04_attack_lab")

console = Console()

_DETAIL_TRUNCATE_LEN = 60


def _verifier_for(outcome: AttackOutcome) -> RootIDVerifier:
    return RootIDVerifier(
        outcome.registry,
        max_clock_skew_ns=10**19,
        freshness_window_ns=10**19,
    )


def main() -> None:
    """Build, verify, and render every attack outcome."""
    console.rule("[bold]KonnexCore — Attack Lab demo[/bold]")

    table = Table(
        title="Five adversarial bundles vs DetVerify",
        show_header=True,
        header_style="bold",
    )
    table.add_column("Attack")
    table.add_column("Expected stage")
    table.add_column("Caught at")
    table.add_column("final_pct", justify="right")
    table.add_column("Verdict")
    table.add_column("Reason")

    all_correct = True
    for name, generator in ATTACK_GENERATORS.items():
        gen: Callable[[], AttackOutcome] = generator  # type: ignore[assignment]
        log.info("running %s ...", name)
        outcome = gen()
        verifier = _verifier_for(outcome)
        result = DetVerifyPipeline(verifier).verify(outcome.bundle)
        last = result.stage_results[-1]
        caught = last.name
        ok = caught == outcome.expected_stage
        all_correct = all_correct and ok and (result.score.final_pct <= VERDICT_FAILURE_THRESHOLD)
        detail = last.detail
        if len(detail) > _DETAIL_TRUNCATE_LEN:
            detail = detail[:_DETAIL_TRUNCATE_LEN] + "..."
        table.add_row(
            name,
            outcome.expected_stage,
            f"[green]{caught}[/green]" if ok else f"[red]{caught}[/red]",
            str(result.score.final_pct),
            result.score.verdict,
            detail,
        )

    console.print(table)

    if all_correct:
        console.print(
            Panel.fit(
                "[bold green]ALL 5 ATTACKS CAUGHT[/bold green]  "
                f"(every final_pct ≤ {VERDICT_FAILURE_THRESHOLD})",
                title="Phase 4",
            ),
        )
        sys.exit(0)
    else:  # pragma: no cover — happy path is the only path here
        console.print(
            Panel.fit(
                "[bold red]ONE OR MORE ATTACKS NOT CAUGHT[/bold red]",
                title="Phase 4",
            ),
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
