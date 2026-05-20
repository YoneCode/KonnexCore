"""DetVerify Stage 5 — Statistical anomaly detection.

A scikit-learn :class:`~sklearn.ensemble.IsolationForest` is fit at
module load time on a deterministic, seeded synthetic baseline of
realistic IMU magnitudes. At verification time we score the bundle's
IMU packets against the trained model. If more than
``ANOMALY_FAIL_THRESHOLD`` of packets are flagged as anomalies, the
stage returns ``severity="warning"`` (does not short-circuit the
pipeline — anomaly is a soft signal at Phase 3).

Production hardening (Phase 8): persist a versioned model artefact
rather than refitting at import; broaden the feature space beyond
||accel||/||gyro||.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from sklearn.ensemble import IsolationForest

from core.models import SensorChannel, StageResult
from detverify._common import decode_imu_packets, packets_for_channel

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from core.models import PoPWBundle

STAGE_NAME = "anomaly"

#: Fraction of IMU packets that may be flagged before the stage warns.
ANOMALY_FAIL_THRESHOLD: float = 0.20

#: Random seed for the baseline synthesis. Determinism is required
#: so two pipelines fitted in different processes agree on the same
#: training distribution.
_BASELINE_SEED: int = 0xCAFE
_BASELINE_SIZE: int = 512
#: Hyperparameters for IsolationForest. Conservative defaults; tuned
#: at Phase 8 against the real validator workload.
_FOREST_KWARGS: dict[str, object] = {
    "n_estimators": 100,
    "contamination": 0.05,
    "random_state": 42,
}


def _vec_norm(v: tuple[float, float, float]) -> float:
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _build_baseline_features(rng: np.random.Generator, n: int) -> NDArray[np.float64]:
    """Synthesize a baseline of (||accel||, ||gyro||) features.

    A real-world IMU at rest reads proper acceleration ~ +g along the
    vertical axis (the support reaction force keeps it from falling).
    The Phase 2 sim engine emits the world-frame velocity of the arm
    base + a gravity offset, so a stationary or slowly-moving roboarm
    produces ||accel|| ≈ g with mild jitter and ||gyro|| ≈ 0. This
    distribution matches that.
    """
    accel_mag = rng.normal(loc=9.81, scale=0.5, size=n).clip(min=0.0)
    gyro_mag = np.abs(rng.normal(loc=0.0, scale=0.3, size=n))
    return np.stack([accel_mag, gyro_mag], axis=1)


def _train_default_model() -> IsolationForest:
    rng = np.random.default_rng(_BASELINE_SEED)
    features = _build_baseline_features(rng, _BASELINE_SIZE)
    model = IsolationForest(**_FOREST_KWARGS)
    model.fit(features)
    return model


# Module-level singleton — fit once, reused across pipeline calls.
# Tests can monkeypatch ``_DEFAULT_MODEL`` if they need a custom one.
_DEFAULT_MODEL: IsolationForest = _train_default_model()


def run(bundle: PoPWBundle, *, model: IsolationForest | None = None) -> StageResult:
    """Run Stage 5."""
    forest = model if model is not None else _DEFAULT_MODEL

    imu_packets = packets_for_channel(bundle, SensorChannel.IMU)
    if not imu_packets:
        return StageResult(
            name=STAGE_NAME,
            passed=True,
            detail="no imu packets to score",
            severity="info",
        )

    try:
        decoded = decode_imu_packets(imu_packets)
    except ValueError as exc:
        return StageResult(
            name=STAGE_NAME,
            passed=False,
            detail=f"imu decode failed: {exc}",
            severity="warning",
        )

    features = np.array(
        [[_vec_norm(accel), _vec_norm(gyro)] for accel, gyro in decoded],
        dtype=np.float64,
    )
    predictions = forest.predict(features)  # +1 normal, -1 anomaly
    n = len(predictions)
    anomalies = int((predictions == -1).sum())
    ratio = anomalies / n
    if ratio > ANOMALY_FAIL_THRESHOLD:
        return StageResult(
            name=STAGE_NAME,
            passed=False,
            detail=(
                f"{anomalies}/{n} ({ratio:.1%}) imu packets flagged as anomalies, "
                f"threshold {ANOMALY_FAIL_THRESHOLD:.1%}"
            ),
            severity="warning",
        )
    return StageResult(
        name=STAGE_NAME,
        passed=True,
        detail=f"{anomalies}/{n} imu packets flagged ({ratio:.1%}); within threshold",
        severity="info",
    )
