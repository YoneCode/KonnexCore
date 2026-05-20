"""Deterministic PyBullet roboarm simulator.

Phase 2 deliverable: drives a Kuka iiwa arm through a short scripted
trajectory, captures camera/IMU/torque streams at fixed sample
points, signs each packet via a Phase 1 ``TEESimulator``, and
assembles the resulting ``PoPWBundle``.

PyBullet is imported lazily so unit tests that only need
``SimConfig`` validation can import this module without the heavy
backend (relevant in CI matrices that haven't installed pybullet).

Determinism notes
-----------------
* ``seed`` controls a numpy RNG used for any explicit noise. The
  PyBullet integrator is itself deterministic when run in
  ``DIRECT`` mode with a fixed timestep and joint command schedule.
* Timestamps are derived from ``base_timestamp_ns`` plus the
  simulation step index times the timestep, so they do not depend
  on the wall clock — same config always yields the same
  ``timestamp_ns`` sequence.
* Cross-platform reproducibility of camera renders is NOT guaranteed
  by PyBullet (different OpenGL drivers, etc.); we therefore only
  assert single-process / same-machine reproducibility in tests.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from core import sensor_codec
from core.models import PolicyTrace, PoPWBundle, SensorChannel
from rootid.did import DID_PATTERN
from rootid.sensor_signer import SensorSigner
from rootid.tee_simulator import TEESimulator

if TYPE_CHECKING:
    from collections.abc import Iterator

log = logging.getLogger(__name__)

#: Physics step size in seconds — fixed at PyBullet's default for determinism.
_PHYSICS_TIMESTEP_S: float = 1.0 / 240.0
_PHYSICS_TIMESTEP_NS: int = int(_PHYSICS_TIMESTEP_S * 1_000_000_000)


class SimConfig(BaseModel):
    """Deterministic configuration for one simulator run."""

    model_config = ConfigDict(extra="forbid")

    robot_did: str = Field(..., pattern=DID_PATTERN.pattern)
    job_id: str = Field(default="sim-job-0001")
    task_prompt: str = Field(default="pick the apple from the pan")
    seed: int = Field(default=42, ge=0)
    num_steps: int = Field(default=60, ge=1, le=10_000)
    capture_every_n_steps: int = Field(default=10, ge=1, le=1000)
    camera_width: int = Field(default=64, ge=16, le=512)
    camera_height: int = Field(default=64, ge=16, le=512)


class SimEngine:
    """PyBullet-backed roboarm simulator.

    The class encapsulates the full lifecycle: connect → load →
    step+capture → disconnect. Re-running ``run()`` on the same
    instance produces a fresh, independent bundle.
    """

    def __init__(self, config: SimConfig, tee: TEESimulator) -> None:
        if config.robot_did != tee.robot_did:
            msg = (
                f"SimConfig.robot_did ({config.robot_did!r}) and "
                f"TEESimulator.robot_did ({tee.robot_did!r}) must match"
            )
            raise ValueError(msg)
        self._config = config
        self._tee = tee
        self._signer = SensorSigner(tee)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, *, base_timestamp_ns: int = 0) -> PoPWBundle:
        """Run the full scenario and return a signed ``PoPWBundle``.

        Args:
            base_timestamp_ns: Anchor for the deterministic timestamp
                sequence. Each captured packet records
                ``base_timestamp_ns + step_index * _PHYSICS_TIMESTEP_NS``.

        Returns:
            A ``PoPWBundle`` whose Merkle root commits to all signed
            sensor packets in capture order.
        """
        cfg = self._config
        rng = np.random.default_rng(cfg.seed)
        log.info(
            "SimEngine.run start: seed=%d num_steps=%d capture_every=%d",
            cfg.seed,
            cfg.num_steps,
            cfg.capture_every_n_steps,
        )

        packets = []
        for step_idx, observation in self._iter_simulation(rng):
            ts = base_timestamp_ns + step_idx * _PHYSICS_TIMESTEP_NS
            cam_payload = sensor_codec.encode_camera_frame(observation["rgba"])
            imu_payload = sensor_codec.encode_imu(
                accel=observation["accel"],
                gyro=observation["gyro"],
            )
            torque_payload = sensor_codec.encode_torque(observation["torques"])
            packets.append(
                self._signer.sign_packet(cfg.job_id, SensorChannel.CAMERA, ts, cam_payload),
            )
            packets.append(
                self._signer.sign_packet(cfg.job_id, SensorChannel.IMU, ts, imu_payload),
            )
            packets.append(
                self._signer.sign_packet(cfg.job_id, SensorChannel.TORQUE, ts, torque_payload),
            )

        if not packets:
            msg = "SimEngine produced zero packets: " "num_steps must be >= capture_every_n_steps"
            raise RuntimeError(msg)

        from datetime import datetime, timezone

        bundle = self._signer.build_bundle(
            job_id=cfg.job_id,
            task_prompt=cfg.task_prompt,
            policy_trace=PolicyTrace(
                actions=[{"step": i} for i in range(cfg.num_steps)],
                seed=cfg.seed,
                policy_hash=("dd" * 32),
            ),
            packets=packets,
            submitted_at=datetime.now(tz=timezone.utc),
        )
        log.info(
            "SimEngine.run done: %d packets, root=%s", len(packets), bundle.bundle_merkle_root[:16]
        )
        return bundle

    # ------------------------------------------------------------------
    # Simulation loop
    # ------------------------------------------------------------------

    def _iter_simulation(
        self,
        rng: np.random.Generator,
    ) -> Iterator[tuple[int, dict[str, Any]]]:
        """Yield ``(step_index, observation)`` at each capture point.

        Imports pybullet lazily; raises ``RuntimeError`` with a clear
        message if the import fails. The DIRECT physics client is
        opened on ``__enter__``-style and torn down even if the
        caller iterates partially.
        """
        try:
            import pybullet as p
            import pybullet_data
        except ImportError as exc:  # pragma: no cover — covered only when pybullet absent
            msg = "pybullet is not installed; run `pip install pybullet`"
            raise RuntimeError(msg) from exc

        client = p.connect(p.DIRECT)
        try:
            self._configure_client(p, client, pybullet_data)
            arm_id, num_joints = self._load_scene(p)
            yield from self._stream_observations(p, arm_id, num_joints, rng)
        finally:
            p.disconnect(client)

    @staticmethod
    def _configure_client(
        p: Any,
        client: int,
        pybullet_data: Any,
    ) -> None:
        p.resetSimulation()
        p.setGravity(0, 0, -9.81)
        p.setTimeStep(_PHYSICS_TIMESTEP_S)
        p.setPhysicsEngineParameter(deterministicOverlappingPairs=1)
        p.setAdditionalSearchPath(pybullet_data.getDataPath())

    def _load_scene(self, p: Any) -> tuple[int, int]:
        # Floor.
        p.loadURDF("plane.urdf")
        # Roboarm.
        arm_id = p.loadURDF(
            "kuka_iiwa/model.urdf",
            basePosition=[0, 0, 0],
            useFixedBase=True,
        )
        num_joints = p.getNumJoints(arm_id)
        # Apple sphere — visual + collision in one body.
        sphere_col = p.createCollisionShape(p.GEOM_SPHERE, radius=0.04)
        sphere_vis = p.createVisualShape(p.GEOM_SPHERE, radius=0.04, rgbaColor=[1, 0, 0, 1])
        p.createMultiBody(
            baseMass=0.05,
            baseCollisionShapeIndex=sphere_col,
            baseVisualShapeIndex=sphere_vis,
            basePosition=[0.5, 0.0, 0.05],
        )
        # Pan — flat cylinder.
        pan_col = p.createCollisionShape(p.GEOM_CYLINDER, radius=0.12, height=0.02)
        pan_vis = p.createVisualShape(
            p.GEOM_CYLINDER,
            radius=0.12,
            length=0.02,
            rgbaColor=[0.2, 0.2, 0.2, 1],
        )
        p.createMultiBody(
            baseMass=0.0,
            baseCollisionShapeIndex=pan_col,
            baseVisualShapeIndex=pan_vis,
            basePosition=[0.5, 0.0, 0.01],
        )
        return arm_id, num_joints

    def _stream_observations(
        self,
        p: Any,
        arm_id: int,
        num_joints: int,
        rng: np.random.Generator,
    ) -> Iterator[tuple[int, dict[str, Any]]]:
        cfg = self._config
        # Drive joints with a deterministic schedule (gentle sinusoid).
        target_amplitudes = rng.uniform(-0.5, 0.5, size=num_joints).astype(np.float64)

        for step in range(cfg.num_steps):
            angle_scale = float(step) / float(cfg.num_steps)
            for j in range(num_joints):
                target = float(target_amplitudes[j]) * angle_scale
                p.setJointMotorControl2(
                    arm_id,
                    j,
                    controlMode=p.POSITION_CONTROL,
                    targetPosition=target,
                    force=200.0,
                )
            p.stepSimulation()

            if (step + 1) % cfg.capture_every_n_steps != 0:
                continue

            yield step, self._capture(p, arm_id, num_joints)

    def _capture(self, p: Any, arm_id: int, num_joints: int) -> dict[str, Any]:
        cfg = self._config
        # Camera: render from a fixed external viewpoint.
        view = p.computeViewMatrix(
            cameraEyePosition=[1.5, 0.0, 0.7],
            cameraTargetPosition=[0.0, 0.0, 0.3],
            cameraUpVector=[0, 0, 1],
        )
        proj = p.computeProjectionMatrixFOV(
            fov=60.0,
            aspect=cfg.camera_width / cfg.camera_height,
            nearVal=0.1,
            farVal=5.0,
        )
        _, _, rgba_raw, _, _ = p.getCameraImage(
            width=cfg.camera_width,
            height=cfg.camera_height,
            viewMatrix=view,
            projectionMatrix=proj,
            renderer=p.ER_TINY_RENDERER,
        )
        rgba = np.asarray(rgba_raw, dtype=np.uint8).reshape(
            cfg.camera_height,
            cfg.camera_width,
            4,
        )

        # IMU: take linear/angular velocity of the arm's base link
        # and synthesize a proper-acceleration reading by adding the
        # gravity offset (a real IMU at rest reads ~+g along z).
        lin, ang = p.getBaseVelocity(arm_id)
        accel: tuple[float, float, float] = (
            float(lin[0]),
            float(lin[1]),
            float(lin[2]) + 9.81,
        )
        gyro: tuple[float, float, float] = (float(ang[0]), float(ang[1]), float(ang[2]))

        # Torque: per-joint applied torque from the joint state.
        joint_states = p.getJointStates(arm_id, list(range(num_joints)))
        torques = tuple(float(state[3]) for state in joint_states)

        return {"rgba": rgba, "accel": accel, "gyro": gyro, "torques": torques}


# ---------------------------------------------------------------------------
# Convenience wrapper + CLI
# ---------------------------------------------------------------------------


def run_demo(
    *,
    seed: int = 42,
    num_steps: int = 60,
    output_path: Path | None = None,
) -> PoPWBundle:
    """Build a fresh ``TEESimulator`` and run a default-config sim.

    Uses ``time.time_ns()`` as the base timestamp so the resulting
    bundle passes a default-window ``RootIDVerifier`` without
    needing custom freshness settings. Tests that need
    deterministic timestamps drive ``SimEngine.run`` directly with
    an explicit ``base_timestamp_ns``.

    If ``output_path`` is given, the resulting bundle is written there
    as JSON (Phase 2 exit-criterion artefact ``bundle.json``).
    """
    import time as _time

    cfg = SimConfig(
        robot_did="did:knx:testnet:sim-robot-demo01",
        seed=seed,
        num_steps=num_steps,
    )
    tee = TEESimulator(robot_did=cfg.robot_did)
    bundle = SimEngine(cfg, tee).run(base_timestamp_ns=_time.time_ns())
    if output_path is not None:
        output_path.write_text(bundle.model_dump_json(indent=2))
        log.info("wrote bundle to %s (%d packets)", output_path, len(bundle.sensor_packets))
    return bundle


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m core.sim_engine",
        description="Run a deterministic roboarm simulation and emit a signed PoPWBundle.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Deterministic seed (default 42).")
    parser.add_argument(
        "--num-steps",
        type=int,
        default=60,
        help="Number of physics steps to simulate (default 60).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("bundle.json"),
        help="Output JSON path (default ./bundle.json).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = _build_arg_parser().parse_args(argv)
    bundle = run_demo(seed=args.seed, num_steps=args.num_steps, output_path=args.out)
    log.info(
        "OK: job_id=%s packets=%d root=%s",
        bundle.job_id,
        len(bundle.sensor_packets),
        bundle.bundle_merkle_root[:16],
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
