"""Tests for real-data loaders.

These tests run against actual downloaded datasets. They are skipped
(not failed) if the data directory is not present — this is the
honest, design spec-compliant posture: we don't mock the data, and we
don't claim passes that didn't happen.

Download instructions for missing datasets are printed in the skip reason.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core import crypto
from core.data_loaders import euroc_loader, tum_loader
from core.models import SensorChannel
from detverify.pipeline import DetVerifyPipeline
from rootid.did import build_did_document
from rootid.registry import IdentityRegistry
from rootid.sensor_signer import SensorSigner
from rootid.tee_simulator import TEESimulator
from rootid.verifier import RootIDVerifier

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"
TUM_DIR = DATA_ROOT / "tum" / "rgbd_dataset_freiburg1_desk"
EUROC_DIR = DATA_ROOT / "euroc" / "MH_01_easy" / "mav0" / ".."  # resolves to MH_01_easy/
BRIDGE_DIR = DATA_ROOT / "bridge"

_TUM_PRESENT = TUM_DIR.exists() and (TUM_DIR / "accelerometer.txt").exists()
_EUROC_PRESENT = (DATA_ROOT / "euroc" / "MH_01_easy" / "mav0" / "imu0" / "data.csv").exists()
_BRIDGE_PRESENT = any(BRIDGE_DIR.glob("**/obs_dict.pkl")) if BRIDGE_DIR.exists() else False


def _make_signer() -> tuple[SensorSigner, IdentityRegistry]:
    """Build a TEE + signer + registered identity for the test."""
    from datetime import datetime, timezone

    tee = TEESimulator(robot_did="did:knx:testnet:real-data-robot")
    signer = SensorSigner(tee)
    registry = IdentityRegistry()
    registry.register(
        build_did_document(
            tee.robot_did,
            public_bytes=tee.public_bytes,
            auth_bytes=tee.public_bytes,
            capabilities=["camera", "imu", "torque"],
            created_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
        ),
    )
    return signer, registry


# ---------------------------------------------------------------------------
# TUM RGB-D
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _TUM_PRESENT,
    reason=(
        "TUM dataset not found. Download with:\n"
        "  wget https://cvg.cit.tum.de/rgbd/dataset/freiburg1/"
        "rgbd_dataset_freiburg1_desk.tgz -O data/tum/desk.tgz\n"
        "  tar xzf data/tum/desk.tgz -C data/tum/"
    ),
)
class TestTumLoader:
    def test_loads_real_imu_packets(self) -> None:
        signer, _ = _make_signer()
        packets = tum_loader.load_imu_packets(
            TUM_DIR,
            signer=signer,
            job_id="tum-imu-test",
            max_packets=100,
        )
        assert len(packets) == 100
        assert all(p.channel == SensorChannel.IMU for p in packets)
        # Timestamps should be monotonically increasing.
        timestamps = [p.timestamp_ns for p in packets]
        assert timestamps == sorted(timestamps)
        # Nonces are 0..99.
        assert [p.nonce for p in packets] == list(range(100))

    def test_imu_packets_have_real_values(self) -> None:
        """The decoded IMU magnitudes should be physically plausible (gravity-scale)."""
        import base64
        import math

        from core import sensor_codec

        signer, _ = _make_signer()
        packets = tum_loader.load_imu_packets(
            TUM_DIR,
            signer=signer,
            job_id="tum-imu-mag",
            max_packets=50,
        )
        for p in packets:
            accel, gyro = sensor_codec.decode_imu(base64.b64decode(p.data_b64))
            mag = math.sqrt(sum(x * x for x in accel))
            # Real IMU at rest reads ~9.81 m/s². TUM data is from a
            # handheld sensor so expect 5-15 m/s² range.
            assert mag > 1.0, f"acceleration magnitude too small: {mag}"
            assert mag < 50.0, f"acceleration magnitude too large: {mag}"

    def test_imu_packets_verify_with_rootid(self) -> None:
        signer, registry = _make_signer()
        packets = tum_loader.load_imu_packets(
            TUM_DIR,
            signer=signer,
            job_id="tum-verify",
            max_packets=20,
        )
        verifier = RootIDVerifier(
            registry,
            max_clock_skew_ns=10**19,
            freshness_window_ns=10**19,
        )
        for p in packets:
            result = verifier.verify_packet(p)
            assert result.valid, f"packet nonce={p.nonce} failed: {result.reason}"

    def test_depth_packets_load(self) -> None:
        signer, _ = _make_signer()
        packets = tum_loader.load_depth_packets(
            TUM_DIR,
            signer=signer,
            job_id="tum-depth",
            max_packets=10,
        )
        assert len(packets) == 10
        assert all(p.channel == SensorChannel.CAMERA for p in packets)

    def test_full_bundle_passes_detverify(self) -> None:
        """End-to-end: TUM data → signed bundle → DetVerify pipeline → score ≥ 80."""
        from datetime import datetime, timezone

        signer, registry = _make_signer()
        job_id = "tum-detverify-e2e"
        imu_packets = tum_loader.load_imu_packets(
            TUM_DIR,
            signer=signer,
            job_id=job_id,
            max_packets=30,
        )
        depth_packets = tum_loader.load_depth_packets(
            TUM_DIR,
            signer=signer,
            job_id=job_id,
            max_packets=10,
        )
        all_packets = imu_packets + depth_packets
        bundle = signer.build_bundle(
            job_id=job_id,
            task_prompt="TUM freiburg1_desk real-data verification",
            policy_trace=__import__("core.models", fromlist=["PolicyTrace"]).PolicyTrace(
                actions=[{"source": "tum"}],
                seed=0,
                policy_hash=crypto.sha3_256(b"tum-real-data").hex(),
            ),
            packets=all_packets,
            submitted_at=datetime.now(tz=timezone.utc),
        )
        verifier = RootIDVerifier(
            registry,
            max_clock_skew_ns=10**19,
            freshness_window_ns=10**19,
        )
        pipeline = DetVerifyPipeline(verifier)
        result = pipeline.verify(bundle)
        assert result.score.final_pct >= 80, (
            f"TUM bundle scored {result.score.final_pct}: " f"{result.score.reasoning}"
        )
        assert result.score.verdict == "success"


# ---------------------------------------------------------------------------
# EuRoC
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _EUROC_PRESENT,
    reason=(
        "EuRoC dataset not found. Download with:\n"
        "  wget http://robotics.ethz.ch/~asl-datasets/ijrr_euroc_mav_dataset/"
        "machine_hall/MH_01_easy/MH_01_easy.zip -O data/euroc/MH_01_easy.zip\n"
        "  unzip data/euroc/MH_01_easy.zip -d data/euroc/MH_01_easy/"
    ),
)
class TestEurocLoader:
    def test_loads_real_imu_packets(self) -> None:
        signer, _ = _make_signer()
        euroc_root = DATA_ROOT / "euroc" / "MH_01_easy"
        packets = euroc_loader.load_imu_packets(
            euroc_root,
            signer=signer,
            job_id="euroc-imu-test",
            max_packets=100,
        )
        assert len(packets) == 100
        assert all(p.channel == SensorChannel.IMU for p in packets)


# ---------------------------------------------------------------------------
# BridgeData
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _BRIDGE_PRESENT,
    reason=(
        "BridgeData not found. Download a trajectory from:\n"
        "  https://rail-berkeley.github.io/bridgedata/\n"
        "  Place obs_dict.pkl at data/bridge/<traj>/obs_dict.pkl"
    ),
)
class TestBridgeLoader:
    def test_loads_trajectory(self) -> None:
        from core.data_loaders import bridge_loader

        signer, _ = _make_signer()
        pkl = next(BRIDGE_DIR.glob("**/obs_dict.pkl"))
        packets = bridge_loader.load_trajectory_packets(
            pkl,
            signer=signer,
            job_id="bridge-test",
            max_packets=20,
        )
        assert len(packets) >= 1
