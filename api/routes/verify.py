"""DetVerify HTTP endpoints — Layer B."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict

from api.deps import AppState, get_state
from core.models import DetVerifyResult, PoPWBundle
from detverify.llm_compare import compare_with_llm

router = APIRouter(prefix="/api/verify", tags=["verify"])


class LlmCompareRequest(BaseModel):
    """Body for ``POST /api/verify/with-llm-compare``."""

    model_config = ConfigDict(extra="forbid")

    bundle: PoPWBundle
    enable_llm: bool = True


@router.post(
    "",
    response_model=DetVerifyResult,
    summary="Run the deterministic six-stage DetVerify pipeline",
    status_code=status.HTTP_200_OK,
)
def verify_bundle(
    bundle: PoPWBundle,
    state: Annotated[AppState, Depends(get_state)],
) -> DetVerifyResult:
    """Run all six DetVerify stages against ``bundle``."""
    return state.pipeline.verify(bundle)


@router.post(
    "/with-llm-compare",
    response_model=DetVerifyResult,
    summary="Run DetVerify and (optionally) compare to a GPT-4o reference",
)
def verify_bundle_with_llm(
    body: LlmCompareRequest,
    state: Annotated[AppState, Depends(get_state)],
) -> DetVerifyResult:
    """Run DetVerify, then attach the LLM-tier verdict if available.

    Falls back to a graceful no-op (``llm_comparison=None``,
    ``layers_agree=None``) when no ``OPENAI_API_KEY`` is set —
    matches the fail-secure stance documented in
    ``detverify/llm_compare.py``.
    """
    result = state.pipeline.verify(body.bundle)
    llm_score = compare_with_llm(body.bundle, enabled=body.enable_llm)
    if llm_score is None:
        return result
    layers_agree = llm_score.verdict == result.score.verdict  # pragma: no cover
    return result.model_copy(  # pragma: no cover — gated behind real OPENAI_API_KEY
        update={"llm_comparison": llm_score, "layers_agree": layers_agree},
    )
