"""End-to-end RootID + Sim Engine demo (Phase 2).

Run::

    python examples/02_sim_bundle.py
    python examples/02_sim_bundle.py --seed 7 --num-steps 100

Drives a simulated Kuka iiwa arm through a deterministic short
trajectory, captures camera + IMU + torque streams, signs each via
the Phase 1 ``TEESimulator``, assembles a ``PoPWBundle``, writes it
to ``bundle.json``, and immediately verifies it through the
``RootIDVerifier`` to prove the artifact is well-formed.
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

# Allow ``python examples/02_sim_bundle.py`` from the project root
# without setting PYTHONPATH.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import click  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.table import Table  # noqa: E402

from core.sim_engine import SimConfig, SimEngine  # noqa: E402
from rootid.did import build_did_document  # noqa: E402
from rootid.registry import IdentityRegistry  # noqa: E402
from rootid.tee_simulator import TEESimulator  # noqa: E402
from rootid.verifier import RootIDVerifier  # noqa: E402

if TYPE_CHECKING:
    from core.models import PoPWBundle

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("02_sim_bundle")

console = Console()


def _render_summary(bundle: PoPWBundle) -> Table:
    table = Table(title="Captured packets by channel", show_header=True, header_style="bold")
    table.add_column("Channel")
    table.add_column("Count", justify="right")
    table.add_column("First nonce", justify="right")
    table.add_column("Last nonce", justify="right")
    by_channel: dict[str, list[int]] = {}
    for p in bundle.sensor_packets:
        by_channel.setdefault(p.channel.value, []).append(p.nonce)
    for chan, nonces in sorted(by_channel.items()):
        table.add_row(chan, str(len(nonces)), str(min(nonces)), str(max(nonces)))
    return table


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--seed", type=int, default=42, help="Deterministic seed (default 42).")
@click.option("--num-steps", type=int, default=60, help="Physics steps to simulate.")
@click.option(
    "--out",
    type=click.Path(dir_okay=False, path_type=Path),
    default=Path("bundle.json"),
    help="Output JSON path.",
)
def main(seed: int, num_steps: int, out: Path) -> None:
    """Run a deterministic sim, sign sensor packets, write+verify the bundle."""
    console.rule("[bold]KonnexCore — Sim Engine demo[/bold]")

    cfg = SimConfig(
        robot_did="did:knx:testnet:sim-demo-02",
        seed=seed,
        num_steps=num_steps,
    )
    tee = TEESimulator(robot_did=cfg.robot_did)

    registry = IdentityRegistry()
    registry.register(
        build_did_document(
            tee.robot_did,
            public_bytes=tee.public_bytes,
            auth_bytes=tee.public_bytes,
            capabilities=["camera", "imu", "torque"],
            created_at=datetime.now(tz=timezone.utc),
        ),
    )

    log.info("running simulation: seed=%d num_steps=%d", seed, num_steps)
    bundle = SimEngine(cfg, tee).run(base_timestamp_ns=time.time_ns())
    out.write_text(bundle.model_dump_json(indent=2))
    log.info("wrote %d packets to %s", len(bundle.sensor_packets), out)

    console.print(
        Panel.fit(
            f"[cyan]robot_did:[/cyan] {bundle.robot_did}\n"
            f"[cyan]job_id:[/cyan] {bundle.job_id}\n"
            f"[cyan]bundle_merkle_root:[/cyan] {bundle.bundle_merkle_root[:32]}...\n"
            f"[cyan]packets:[/cyan] {len(bundle.sensor_packets)}",
            title="Bundle",
        ),
    )
    console.print(_render_summary(bundle))

    # Verify the freshly written bundle through the same verifier the
    # Phase 1 example uses. Wide windows so the demo doesn't trip on
    # absolute timestamps (sim uses base_timestamp_ns=0 by default).
    verifier = RootIDVerifier(registry, freshness_window_ns=10**18, max_clock_skew_ns=10**18)
    result = verifier.verify_bundle(bundle)

    if result.valid:
        console.print(
            Panel.fit(
                f"[bold green]VALID[/bold green]  reason={result.reason}",
                title="Verifier",
            ),
        )
        sys.exit(0)
    else:  # pragma: no cover — happy path is the only path here
        console.print(
            Panel.fit(
                f"[bold red]INVALID[/bold red]  reason={result.reason}",
                title="Verifier",
            ),
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
