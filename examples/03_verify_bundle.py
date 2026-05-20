"""End-to-end DetVerify demo (Phase 3).

Run::

    python examples/03_verify_bundle.py
    python examples/03_verify_bundle.py --tamper signature
    python examples/03_verify_bundle.py --tamper torque

The happy path runs the Phase 2 ``SimEngine`` to produce a clean
signed ``PoPWBundle``, then runs all six DetVerify stages and prints
the resulting Konnex ``ScoreVector``. The clean path exits 0 with
``final_pct >= 80`` (Phase 3 spec exit criterion). With ``--tamper``,
one packet is mutated before verification; the score should drop to
``final_pct <= 30`` with a precise stage-failure reason.
"""

from __future__ import annotations

import base64
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Literal

# sys.path bootstrap so this script runs without PYTHONPATH.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import click  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.table import Table  # noqa: E402

from core import sensor_codec  # noqa: E402
from core.models import SensorChannel  # noqa: E402
from core.sim_engine import SimConfig, SimEngine  # noqa: E402
from detverify.pipeline import DetVerifyPipeline  # noqa: E402
from rootid.did import build_did_document  # noqa: E402
from rootid.registry import IdentityRegistry  # noqa: E402
from rootid.tee_simulator import TEESimulator  # noqa: E402
from rootid.verifier import RootIDVerifier  # noqa: E402

if TYPE_CHECKING:
    from core.models import DetVerifyResult, PoPWBundle

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("03_verify_bundle")

console = Console()

TamperMode = Literal["none", "signature", "torque"]


def _build_clean(seed: int, num_steps: int) -> tuple[PoPWBundle, RootIDVerifier]:
    cfg = SimConfig(
        robot_did="did:knx:testnet:detverify-demo-03",
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
    bundle = SimEngine(cfg, tee).run(base_timestamp_ns=time.time_ns())
    return bundle, RootIDVerifier(registry)


def _apply_tamper(bundle: PoPWBundle, mode: TamperMode) -> PoPWBundle:
    if mode == "none":
        return bundle
    if mode == "signature":
        log.warning("tampering: flipping a bit in packet[0].signature_hex")
        sig = bytearray(bytes.fromhex(bundle.sensor_packets[0].signature_hex))
        sig[0] ^= 0x80
        evil = bundle.sensor_packets[0].model_copy(
            update={"signature_hex": bytes(sig).hex()},
        )
        return bundle.model_copy(
            update={"sensor_packets": [evil, *bundle.sensor_packets[1:]]},
        )
    # mode == "torque" — exhausts the Literal["none", "signature", "torque"].
    log.warning("tampering: replacing a torque packet with a 99 999 N·m payload")
    torque_packets = [
        (i, p) for i, p in enumerate(bundle.sensor_packets) if p.channel == SensorChannel.TORQUE
    ]
    idx, original = torque_packets[0]
    evil_payload = sensor_codec.encode_torque(tuple([99_999.0] * 7))
    evil = original.model_copy(
        update={"data_b64": base64.b64encode(evil_payload).decode("ascii")},
    )
    new_packets = list(bundle.sensor_packets)
    new_packets[idx] = evil
    return bundle.model_copy(update={"sensor_packets": new_packets})


def _render_score(result: DetVerifyResult) -> Table:
    score = result.score
    table = Table(title="Konnex ScoreVector", show_header=True, header_style="bold")
    table.add_column("Field")
    table.add_column("Value", justify="right")
    for field in (
        "accuracy",
        "speed",
        "safety",
        "optimal_track",
        "energy_efficiency",
        "trajectory_stability",
        "final_pct",
    ):
        table.add_row(field, str(getattr(score, field)))
    table.add_row("verdict", score.verdict)
    return table


_DETAIL_TRUNCATE_LEN = 60


def _render_stages(result: DetVerifyResult) -> Table:
    table = Table(title="Stage results", show_header=True, header_style="bold")
    table.add_column("Stage")
    table.add_column("Passed")
    table.add_column("Severity")
    table.add_column("Detail")
    for stage in result.stage_results:
        detail = stage.detail
        if len(detail) > _DETAIL_TRUNCATE_LEN:
            detail = detail[:_DETAIL_TRUNCATE_LEN] + "..."
        table.add_row(
            stage.name,
            "✓" if stage.passed else "✗",
            stage.severity,
            detail,
        )
    return table


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--seed", type=int, default=42)
@click.option("--num-steps", type=int, default=30)
@click.option(
    "--tamper",
    type=click.Choice(["none", "signature", "torque"]),
    default="none",
)
def main(seed: int, num_steps: int, tamper: TamperMode) -> None:
    """Run sim → DetVerify pipeline → print Konnex ScoreVector."""
    console.rule("[bold]KonnexCore — DetVerify demo[/bold]")

    bundle, rootid_verifier = _build_clean(seed, num_steps)
    bundle = _apply_tamper(bundle, tamper)

    pipeline = DetVerifyPipeline(rootid_verifier)
    result = pipeline.verify(bundle)

    console.print(
        Panel.fit(
            f"[cyan]robot_did:[/cyan] {bundle.robot_did}\n"
            f"[cyan]job_id:[/cyan] {bundle.job_id}\n"
            f"[cyan]packets:[/cyan] {len(bundle.sensor_packets)}\n"
            f"[cyan]tamper:[/cyan] {tamper}",
            title="Bundle",
        ),
    )
    console.print(_render_stages(result))
    console.print(_render_score(result))

    score = result.score
    if score.verdict == "success":
        console.print(
            Panel.fit(
                f"[bold green]VERDICT: success[/bold green]  final_pct={score.final_pct}",
                title="DetVerify",
            ),
        )
        sys.exit(0)
    else:
        console.print(
            Panel.fit(
                f"[bold red]VERDICT: {score.verdict}[/bold red]  final_pct={score.final_pct}",
                title="DetVerify",
            ),
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
