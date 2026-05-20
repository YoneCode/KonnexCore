"""End-to-end RootID demo (Phase 1).

Run::

    python examples/01_sign_sensor.py
    python examples/01_sign_sensor.py --tamper signature
    python examples/01_sign_sensor.py --tamper merkle
    python examples/01_sign_sensor.py --tamper job

The happy path constructs a TEE-simulated robot, signs three sensor
packets across distinct channels, assembles a ``PoPWBundle``, and
verifies it. ``--tamper`` simulates an adversarial bundle and exits
non-zero when the verifier catches it (which it always does — that's
the demo).
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

# Allow ``python examples/01_sign_sensor.py`` from the project root
# without setting PYTHONPATH. Examples are user-facing entry points;
# we accept the small sys.path manipulation in exchange for one-step
# runnability. Production callers always import via ``rootid.*``.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import click  # noqa: E402  (after sys.path)
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.table import Table  # noqa: E402

from core.models import PolicyTrace, PoPWBundle, SensorChannel  # noqa: E402
from rootid.did import build_did_document  # noqa: E402
from rootid.registry import IdentityRegistry  # noqa: E402
from rootid.sensor_signer import SensorSigner  # noqa: E402
from rootid.tee_simulator import TEESimulator  # noqa: E402
from rootid.verifier import RootIDVerifier  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("01_sign_sensor")

console = Console()

TamperMode = Literal["none", "signature", "merkle", "job"]


def _build_demo_bundle(
    tamper: TamperMode,
) -> tuple[IdentityRegistry, SensorSigner, PoPWBundle]:
    robot_did = "did:knx:testnet:demo-robot-aaaa"
    tee = TEESimulator(robot_did=robot_did)
    signer = SensorSigner(tee)

    registry = IdentityRegistry()
    registry.register(
        build_did_document(
            tee.robot_did,
            public_bytes=tee.public_bytes,
            auth_bytes=tee.public_bytes,
            capabilities=["camera", "imu", "gps"],
            created_at=datetime.now(tz=timezone.utc),
        ),
    )

    job_id = "demo-job-0001"
    base_ts = time.time_ns()
    packets = [
        signer.sign_packet(job_id, SensorChannel.CAMERA, base_ts + 1, b"frame-cam"),
        signer.sign_packet(job_id, SensorChannel.IMU, base_ts + 2, b"imu-sample"),
        signer.sign_packet(job_id, SensorChannel.GPS, base_ts + 3, b"gps-fix"),
    ]

    bundle = signer.build_bundle(
        job_id=job_id,
        task_prompt="pick the apple from the pan",
        policy_trace=PolicyTrace(
            actions=[{"step": i} for i in range(3)],
            seed=42,
            policy_hash="dd" * 32,
        ),
        packets=packets,
        submitted_at=datetime.now(tz=timezone.utc),
    )

    if tamper == "signature":
        log.warning("Tampering: flipping a bit in packet[0].signature_hex")
        sig = bytearray(bytes.fromhex(packets[0].signature_hex))
        sig[0] ^= 0x80
        evil_packet = packets[0].model_copy(update={"signature_hex": bytes(sig).hex()})
        bundle = bundle.model_copy(
            update={"sensor_packets": [evil_packet, packets[1], packets[2]]},
        )
    elif tamper == "merkle":
        log.warning("Tampering: replacing bundle_merkle_root with garbage")
        bundle = bundle.model_copy(update={"bundle_merkle_root": "ee" * 32})
    elif tamper == "job":
        log.warning("Tampering: changing bundle.job_id without re-signing")
        bundle = bundle.model_copy(update={"job_id": "wrong-job"})

    return registry, signer, bundle


def _render_bundle_table(bundle: PoPWBundle) -> Table:
    table = Table(title="Sensor packets", show_header=True, header_style="bold")
    table.add_column("Channel")
    table.add_column("Nonce", justify="right")
    table.add_column("Timestamp (ns)", justify="right")
    table.add_column("Signature (first 16 hex)")
    for p in bundle.sensor_packets:
        table.add_row(
            p.channel.value,
            str(p.nonce),
            str(p.timestamp_ns),
            p.signature_hex[:16] + "...",
        )
    return table


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--tamper",
    type=click.Choice(["none", "signature", "merkle", "job"]),
    default="none",
    help="Inject a tampering before verification (for the adversarial demo).",
)
def main(tamper: TamperMode) -> None:
    """Sign three sensor packets, build a bundle, and verify it."""
    console.rule("[bold]KonnexCore — RootID demo[/bold]")

    registry, signer, bundle = _build_demo_bundle(tamper)

    console.print(
        Panel.fit(
            f"[cyan]robot_did:[/cyan] {signer.robot_did}\n"
            f"[cyan]job_id:[/cyan] {bundle.job_id}\n"
            f"[cyan]bundle_merkle_root:[/cyan] {bundle.bundle_merkle_root[:32]}...",
            title="Bundle metadata",
        ),
    )
    console.print(_render_bundle_table(bundle))

    verifier = RootIDVerifier(registry)
    result = verifier.verify_bundle(bundle)

    if result.valid:
        console.print(
            Panel.fit(
                f"[bold green]VALID[/bold green]  reason={result.reason}",
                title="Verifier",
            ),
        )
        sys.exit(0)
    else:
        console.print(
            Panel.fit(
                f"[bold red]INVALID[/bold red]  reason={result.reason}",
                title="Verifier",
            ),
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
