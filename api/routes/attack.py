"""Attack lab HTTP endpoints — runs the Phase 4 generators."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from core import attack_lab
from core.models import PoPWBundle

router = APIRouter(prefix="/api/attack", tags=["attack"])


class AttackResponse(BaseModel):
    """Composite response: the adversarial bundle plus its expected catch site."""

    model_config = ConfigDict(extra="forbid")

    bundle: PoPWBundle
    expected_stage: str
    narrative: str


_GENERATORS = {
    "deepfake": attack_lab.make_deepfake_video_bundle,
    "replay": attack_lab.make_replayed_imu_bundle,
    "gps_spoof": attack_lab.make_gps_spoof_bundle,
    "frame_skip": attack_lab.make_frame_skip_bundle,
    "torque_mismatch": attack_lab.make_torque_mismatch_bundle,
}


@router.post(
    "/generate/{attack_type}",
    response_model=AttackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate one of the five Phase 4 adversarial bundles",
)
def generate_attack(attack_type: str) -> AttackResponse:
    """Run the requested attack generator and return ``(bundle, expected_stage)``."""
    generator = _GENERATORS.get(attack_type)
    if generator is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "unknown-attack-type",
                "attack_type": attack_type,
                "valid": sorted(_GENERATORS.keys()),
            },
        )
    outcome = generator()
    return AttackResponse(
        bundle=outcome.bundle,
        expected_stage=outcome.expected_stage,
        narrative=outcome.narrative,
    )
