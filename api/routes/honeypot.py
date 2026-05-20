"""Honeynet HTTP endpoints — Layer C."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from api.deps import AppState, get_state
from core.models import HoneypotTask, ValidatorMetascore, ValidatorVote
from honeynet.generators.roboarm_gen import make_roboarm_honeypot

router = APIRouter(prefix="/api/honeypot", tags=["honeypot"])


class GenerateHoneypotRequest(BaseModel):
    """Body for ``POST /api/honeypot/generate``."""

    model_config = ConfigDict(extra="forbid")

    seed: int = 42
    idx: int = 0
    deadline_s: int = 60
    reward_test_knx: float = 1.0


class SubmitVoteResponse(BaseModel):
    """Response for ``POST /api/honeypot/submit-vote``."""

    model_config = ConfigDict(extra="forbid")

    recorded: bool


@router.post(
    "/generate",
    response_model=HoneypotTask,
    status_code=status.HTTP_201_CREATED,
    summary="Generate one deterministic roboarm honeypot and register it with the oracle",
)
def generate_honeypot(
    body: GenerateHoneypotRequest,
    state: Annotated[AppState, Depends(get_state)],
) -> HoneypotTask:
    """Build a roboarm honeypot and stash its ground truth in the oracle."""
    task = make_roboarm_honeypot(
        seed=body.seed,
        idx=body.idx,
        deadline_s=body.deadline_s,
        reward_test_knx=body.reward_test_knx,
    )
    state.oracle.register_honeypot(task)
    return task


@router.post(
    "/submit-vote",
    response_model=SubmitVoteResponse,
    summary="Record a validator vote with the oracle",
)
def submit_vote(
    vote: ValidatorVote,
    state: Annotated[AppState, Depends(get_state)],
) -> SubmitVoteResponse:
    """Record one validator vote in the oracle's history."""
    state.oracle.submit_vote(vote)
    return SubmitVoteResponse(recorded=True)


@router.get(
    "/metascore/{validator:path}",
    response_model=ValidatorMetascore,
    summary="Compute the metascore S(V) for a validator",
)
def get_metascore(
    validator: str,
    state: Annotated[AppState, Depends(get_state)],
) -> ValidatorMetascore:
    """Return ``ValidatorMetascore`` for ``validator``.

    Returns a zero-sample metascore if the validator hasn't voted yet —
    this is the same behaviour the underlying oracle exposes.
    """
    metascore = state.oracle.compute_metascore(validator)
    if metascore.sample_count == 0 and validator not in state.oracle.known_validators():
        # Surface 404 only if the validator never voted at all. A
        # validator that voted exclusively on organic tasks legitimately
        # has zero honeypot samples but a meaningful consensus term —
        # don't 404 those.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "unknown-validator", "validator_did": validator},
        )
    return metascore


@router.get(
    "/leaderboard",
    response_model=list[ValidatorMetascore],
    summary="Per-validator metascore leaderboard",
)
def get_leaderboard(
    state: Annotated[AppState, Depends(get_state)],
) -> list[ValidatorMetascore]:
    """Return all known validators' metascores, sorted by ``S(V)`` desc."""
    rows = [state.oracle.compute_metascore(did) for did in state.oracle.known_validators()]
    rows.sort(key=lambda m: m.metascore, reverse=True)
    return rows
