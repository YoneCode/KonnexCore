"""Demo HTTP endpoints — composite flows for the dashboard."""

from __future__ import annotations

import time
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from api.deps import AppState, get_state
from core.attack_lab import (
    AttackOutcome,
    make_deepfake_video_bundle,
    make_frame_skip_bundle,
    make_gps_spoof_bundle,
    make_replayed_imu_bundle,
    make_torque_mismatch_bundle,
)
from core.models import DetVerifyResult, PoPWBundle
from core.sim_engine import SimConfig, SimEngine
from rootid.did import build_did_document
from rootid.tee_simulator import TEESimulator
from rootid.verifier import RootIDVerifier

router = APIRouter(prefix="/api/demo", tags=["demo"])


class DemoScenario(BaseModel):
    """One row in the scenarios list."""

    model_config = ConfigDict(extra="forbid")

    key: Literal[
        "clean",
        "deepfake",
        "replay",
        "gps_spoof",
        "frame_skip",
        "torque_mismatch",
    ]
    title: str
    expected_verdict: Literal["success", "failure", "inconclusive"]


class DemoRunResult(BaseModel):
    """Composite Layer A + Layer B result for the dashboard."""

    model_config = ConfigDict(extra="forbid")

    scenario: str
    detverify: DetVerifyResult
    expected_stage: str | None = None
    narrative: str | None = None


_ATTACK_BUILDERS = {
    "deepfake": make_deepfake_video_bundle,
    "replay": make_replayed_imu_bundle,
    "gps_spoof": make_gps_spoof_bundle,
    "frame_skip": make_frame_skip_bundle,
    "torque_mismatch": make_torque_mismatch_bundle,
}


@router.get(
    "/scenarios",
    response_model=list[DemoScenario],
    summary="List the available demo scenarios",
)
def list_scenarios() -> list[DemoScenario]:
    """Return the canonical 6 demo scenario descriptors."""
    return [
        DemoScenario(key="clean", title="Honest signed bundle", expected_verdict="success"),
        DemoScenario(key="deepfake", title="Deepfake video", expected_verdict="failure"),
        DemoScenario(key="replay", title="Replayed IMU", expected_verdict="failure"),
        DemoScenario(key="gps_spoof", title="GPS spoof", expected_verdict="failure"),
        DemoScenario(key="frame_skip", title="Frame skip", expected_verdict="failure"),
        DemoScenario(
            key="torque_mismatch",
            title="Torque mismatch",
            expected_verdict="failure",
        ),
    ]


class FullStackRequest(BaseModel):
    """Body for ``POST /api/demo/full-stack``."""

    model_config = ConfigDict(extra="forbid")

    scenario: Literal[
        "clean",
        "deepfake",
        "replay",
        "gps_spoof",
        "frame_skip",
        "torque_mismatch",
    ] = "clean"
    seed: int = 42


def _build_clean_bundle_and_register(
    state: AppState,
    seed: int,
) -> tuple[PoPWBundle, TEESimulator]:
    """Build a clean SimEngine bundle and register the robot identity."""
    cfg = SimConfig(
        robot_did="did:knx:testnet:demo-fullstack",
        seed=seed,
        num_steps=20,
        capture_every_n_steps=10,
        camera_width=32,
        camera_height=32,
    )
    tee = TEESimulator(robot_did=cfg.robot_did)
    if cfg.robot_did not in state.registry:
        state.registry.register(
            build_did_document(
                tee.robot_did,
                public_bytes=tee.public_bytes,
                auth_bytes=tee.public_bytes,
                capabilities=["camera", "imu", "torque"],
                created_at=__import__("datetime").datetime.now(
                    tz=__import__("datetime").timezone.utc,
                ),
            ),
        )
    bundle = SimEngine(cfg, tee).run(base_timestamp_ns=time.time_ns())
    return bundle, tee


@router.post(
    "/full-stack",
    response_model=DemoRunResult,
    summary="Run a full-stack demo (RootID → DetVerify) for one scenario",
)
def run_full_stack(
    body: FullStackRequest,
    state: Annotated[AppState, Depends(get_state)],
) -> DemoRunResult:
    """Build a bundle for the requested scenario and run it through DetVerify."""
    if body.scenario == "clean":
        bundle, _ = _build_clean_bundle_and_register(state, body.seed)
        result = state.pipeline.verify(bundle)
        return DemoRunResult(scenario="clean", detverify=result)

    builder = _ATTACK_BUILDERS[body.scenario]
    outcome: AttackOutcome = builder()
    # Use the attacker's own registry — the legitimate keypair is the
    # one that signed the (genuine) packets the attacker tampered with.
    verifier = RootIDVerifier(
        outcome.registry,
        max_clock_skew_ns=10**19,
        freshness_window_ns=10**19,
    )
    from detverify.pipeline import DetVerifyPipeline

    pipeline = DetVerifyPipeline(verifier)
    result = pipeline.verify(outcome.bundle)
    return DemoRunResult(
        scenario=body.scenario,
        detverify=result,
        expected_stage=outcome.expected_stage,
        narrative=outcome.narrative,
    )
