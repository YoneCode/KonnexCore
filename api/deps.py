"""Shared FastAPI application state.

The KonnexCore backend holds three persistent objects across request
lifecycles:

* ``IdentityRegistry`` (Layer A) — the mock RobotIdentity contract.
* ``HoneynetOracle`` (Layer C) — vote bookkeeper + metascore composer.
* ``DetVerifyPipeline`` (Layer B) — the verifier wrapping a
  :class:`RootIDVerifier` over the identity registry.

A *server-side TEE pool* (``dict[did, TEESimulator]``) lets the demo
expose ``/api/identity/sign-bundle`` without requiring callers to ship
private keys. **This is a demo affordance.** Production deployments
keep keys inside the robot's hardware secure element; the
``rootid/tee_simulator.py`` interface is the swap-in seam.

Test fixtures construct an ``AppState`` with the same shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Request

from detverify.pipeline import DetVerifyPipeline
from honeynet.oracle import HoneynetOracle
from rootid.registry import IdentityRegistry
from rootid.tee_simulator import TEESimulator
from rootid.verifier import RootIDVerifier

_DEFAULT_FRESHNESS_NS: int = 10**19  # ~317 years; demo accepts dated bundles
_DEFAULT_SKEW_NS: int = 10**19


@dataclass
class AppState:
    """Container for everything the request handlers depend on."""

    registry: IdentityRegistry = field(default_factory=IdentityRegistry)
    oracle: HoneynetOracle = field(default_factory=HoneynetOracle)
    tee_pool: dict[str, TEESimulator] = field(default_factory=dict)
    pipeline: DetVerifyPipeline = field(init=False)

    def __post_init__(self) -> None:
        self.pipeline = DetVerifyPipeline(
            RootIDVerifier(
                self.registry,
                max_clock_skew_ns=_DEFAULT_SKEW_NS,
                freshness_window_ns=_DEFAULT_FRESHNESS_NS,
            ),
        )


def get_state(request: Request) -> AppState:
    """FastAPI dependency: pull the shared :class:`AppState` from the app."""
    state = request.app.state.konnexcore_state
    if not isinstance(state, AppState):  # pragma: no cover — lifespan guards this
        msg = "konnexcore_state is not set; did the lifespan run?"
        raise RuntimeError(msg)
    return state
