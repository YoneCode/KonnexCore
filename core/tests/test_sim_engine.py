"""Tests for ``core/sim_engine.py``.

Slow integration tests (``@pytest.mark.slow``) actually start the
PyBullet ``DIRECT`` backend, load URDFs, and step physics. Fast tests
exercise ``SimConfig`` validation and decoded-payload semantics
without booting the simulator.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from core import sensor_codec
from core.models import PoPWBundle, SensorChannel
from core.sim_engine import SimConfig, SimEngine, run_demo
from rootid.did import build_did_document
from rootid.registry import IdentityRegistry
from rootid.tee_simulator import TEESimulator
from rootid.verifier import RootIDVerifier

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# SimConfig — fast validation tests
# ---------------------------------------------------------------------------


class TestSimConfig:
    def test_defaults(self) -> None:
        cfg = SimConfig(robot_did="did:knx:testnet:sim-robot-aaaa")
        assert cfg.seed == 42
        assert cfg.num_steps == 60
        assert cfg.capture_every_n_steps == 10
        assert cfg.camera_width == 64
        assert cfg.camera_height == 64
        assert cfg.job_id == "sim-job-0001"
        assert cfg.task_prompt

    def test_robot_did_required(self) -> None:
        with pytest.raises(ValidationError):
            SimConfig()  # type: ignore[call-arg]

    def test_robot_did_pattern_enforced(self) -> None:
        with pytest.raises(ValidationError):
            SimConfig(robot_did="not-a-did")

    def test_negative_seed_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SimConfig(robot_did="did:knx:testnet:sim-aaaa", seed=-1)

    def test_zero_steps_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SimConfig(robot_did="did:knx:testnet:sim-aaaa", num_steps=0)

    def test_too_many_steps_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SimConfig(robot_did="did:knx:testnet:sim-aaaa", num_steps=10_001)

    def test_capture_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SimConfig(robot_did="did:knx:testnet:sim-aaaa", capture_every_n_steps=0)


class TestSimEngineGuards:
    def test_constructor_rejects_did_mismatch(self) -> None:
        cfg = SimConfig(robot_did="did:knx:testnet:cfg-aaaa")
        tee = TEESimulator(robot_did="did:knx:testnet:tee-bbbb")
        with pytest.raises(ValueError, match="must match"):
            SimEngine(cfg, tee)

    @pytest.mark.slow
    def test_no_packets_raises(self) -> None:
        # num_steps=1, capture_every_n_steps=2 → no capture point hit.
        tee, _ = _make_registered_tee()
        cfg = SimConfig(
            robot_did=tee.robot_did,
            num_steps=1,
            capture_every_n_steps=2,
            camera_width=32,
            camera_height=32,
        )
        with pytest.raises(RuntimeError, match="zero packets"):
            SimEngine(cfg, tee).run()


@pytest.mark.slow
class TestCli:
    def test_main_writes_bundle_json(self, tmp_path: Path) -> None:
        from core.sim_engine import main

        out = tmp_path / "bundle.json"
        rc = main(["--seed", "5", "--num-steps", "10", "--out", str(out)])
        assert rc == 0
        assert out.exists()
        loaded = PoPWBundle.model_validate_json(out.read_text())
        assert len(loaded.sensor_packets) >= 3


# ---------------------------------------------------------------------------
# SimEngine — slow integration tests
# ---------------------------------------------------------------------------


def _make_registered_tee() -> tuple[TEESimulator, IdentityRegistry]:
    from datetime import datetime, timezone

    tee = TEESimulator(robot_did="did:knx:testnet:sim-robot-bbbb")
    registry = IdentityRegistry()
    registry.register(
        build_did_document(
            tee.robot_did,
            public_bytes=tee.public_bytes,
            auth_bytes=tee.public_bytes,
            capabilities=["camera", "imu", "torque"],
            created_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
        ),
    )
    return tee, registry


@pytest.mark.slow
class TestSimEngineIntegration:
    def test_run_produces_nonempty_bundle(self) -> None:
        tee, _ = _make_registered_tee()
        cfg = SimConfig(
            robot_did=tee.robot_did,
            num_steps=20,
            capture_every_n_steps=10,
            camera_width=32,
            camera_height=32,
        )
        engine = SimEngine(cfg, tee)
        bundle = engine.run()
        assert isinstance(bundle, PoPWBundle)
        assert len(bundle.sensor_packets) >= 3  # at least one of each channel
        assert {p.channel for p in bundle.sensor_packets} == {
            SensorChannel.CAMERA,
            SensorChannel.IMU,
            SensorChannel.TORQUE,
        }

    def test_run_bundle_verifies(self) -> None:
        tee, registry = _make_registered_tee()
        cfg = SimConfig(
            robot_did=tee.robot_did,
            num_steps=20,
            capture_every_n_steps=10,
            camera_width=32,
            camera_height=32,
        )
        bundle = SimEngine(cfg, tee).run()
        # The bundle's timestamps are deterministic and rooted at
        # ``base_timestamp_ns`` (default 0); use a future ``now_ns`` so
        # freshness passes.
        now_ns = max(p.timestamp_ns for p in bundle.sensor_packets) + 1_000_000_000
        verifier = RootIDVerifier(
            registry,
            freshness_window_ns=10**18,
            max_clock_skew_ns=10**18,
        )
        result = verifier.verify_bundle(bundle, now_ns=now_ns)
        assert result.valid is True, result

    def test_run_is_deterministic(self) -> None:
        cfg = SimConfig(
            robot_did="did:knx:testnet:sim-robot-cccc",
            num_steps=20,
            capture_every_n_steps=10,
            camera_width=32,
            camera_height=32,
            seed=7,
        )
        # Two TEEs with the SAME pub/private key would be needed to
        # produce identical signatures; we instead assert determinism
        # of the canonical pre-hash payloads (the parts that depend on
        # the simulator only, not on the per-instance keypair).
        tee_a = TEESimulator(robot_did=cfg.robot_did)
        tee_b = TEESimulator(robot_did=cfg.robot_did)
        bundle_a = SimEngine(cfg, tee_a).run()
        bundle_b = SimEngine(cfg, tee_b).run()
        # The encoded data_b64 fields should match — they depend only
        # on the deterministic simulator output, not the keypair.
        for pa, pb in zip(
            bundle_a.sensor_packets,
            bundle_b.sensor_packets,
            strict=True,
        ):
            assert pa.channel == pb.channel
            assert pa.timestamp_ns == pb.timestamp_ns
            assert pa.data_b64 == pb.data_b64

    def test_decoded_camera_frame_has_expected_shape(self) -> None:
        tee, _ = _make_registered_tee()
        cfg = SimConfig(
            robot_did=tee.robot_did,
            num_steps=10,
            capture_every_n_steps=10,
            camera_width=32,
            camera_height=24,
        )
        bundle = SimEngine(cfg, tee).run()
        cam_packets = [p for p in bundle.sensor_packets if p.channel == SensorChannel.CAMERA]
        assert cam_packets
        import base64

        frame = sensor_codec.decode_camera_frame(base64.b64decode(cam_packets[0].data_b64))
        assert frame.shape == (24, 32, 4)  # H, W, C(=RGBA)


# ---------------------------------------------------------------------------
# run_demo + JSON output (exit criterion)
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestRunDemo:
    def test_run_demo_returns_bundle(self) -> None:
        bundle = run_demo(seed=1, num_steps=10)
        assert isinstance(bundle, PoPWBundle)

    def test_run_demo_writes_json_file(self, tmp_path: Path) -> None:
        out = tmp_path / "bundle.json"
        bundle = run_demo(seed=2, num_steps=10, output_path=out)
        assert out.exists()
        # Round-trip via the model — exit-criterion check.
        loaded = PoPWBundle.model_validate_json(out.read_text())
        assert loaded == bundle
        # Sanity: the file is valid JSON.
        json.loads(out.read_text())
