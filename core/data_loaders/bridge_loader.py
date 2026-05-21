"""BridgeData v2 dataset loader.

Reads BridgeData v2 pickle format where each trajectory directory
contains an obs_dict.pkl with keys like:
  - "images0" → np.ndarray (T, H, W, 3) uint8
  - "state" → np.ndarray (T, state_dim) float — joint positions/velocities

We emit camera frames as CAMERA SensorPackets and joint states as
TORQUE SensorPackets (using the state vector as the torque proxy —
BridgeData doesn't record per-joint torques directly, but the state
vector is the closest physical signal available).

Reference: https://rail-berkeley.github.io/bridgedata/
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path

import numpy as np

from core import sensor_codec
from core.models import SensorChannel, SensorPacket
from rootid.sensor_signer import SensorSigner

log = logging.getLogger(__name__)

#: Synthetic timestep spacing for BridgeData (30 Hz control rate).
_STEP_NS: int = 33_333_333  # ~30 Hz


def load_trajectory_packets(
    pkl_path: Path,
    *,
    signer: SensorSigner,
    job_id: str,
    max_packets: int | None = None,
    resize: tuple[int, int] = (64, 64),
    base_timestamp_ns: int = 0,
) -> list[SensorPacket]:
    """Read obs_dict.pkl and yield signed SensorPackets.

    Emits pairs of (CAMERA, TORQUE) packets per timestep.
    """
    if not pkl_path.exists():
        msg = f"obs_dict.pkl not found at {pkl_path}"
        raise FileNotFoundError(msg)

    with pkl_path.open("rb") as f:
        obs_dict = pickle.load(f)  # noqa: S301 — trusted dataset file

    # BridgeData v2 keys vary; common ones:
    images_key = _find_key(obs_dict, ["images0", "image", "images", "agentview_image"])
    state_key = _find_key(obs_dict, ["state", "qpos", "joint_states", "robot_state"])

    if images_key is None and state_key is None:
        msg = f"No recognized keys in {pkl_path}. Keys: {list(obs_dict.keys())}"
        raise ValueError(msg)

    from PIL import Image

    images = obs_dict.get(images_key) if images_key else None
    states = obs_dict.get(state_key) if state_key else None
    n_steps = len(images) if images is not None else (len(states) if states is not None else 0)

    packets: list[SensorPacket] = []
    for t in range(n_steps):
        ts_ns = base_timestamp_ns + t * _STEP_NS

        if images is not None:
            frame = images[t]
            if frame.dtype != np.uint8:
                frame = np.clip(frame, 0, 255).astype(np.uint8)
            # Resize if needed.
            if frame.shape[:2] != resize:
                pil_img = Image.fromarray(frame).resize(resize, Image.Resampling.BILINEAR)
                frame = np.asarray(pil_img, dtype=np.uint8)
            if frame.ndim == 2:  # noqa: PLR2004
                frame = np.stack([frame, frame, frame], axis=-1)
            payload = sensor_codec.encode_camera_frame(frame)
            packets.append(
                signer.sign_packet(job_id, SensorChannel.CAMERA, ts_ns, payload),
            )

        if states is not None:
            state_vec = states[t]
            # Clamp to max 255 joints (sensor_codec torque limit).
            torques = tuple(float(x) for x in state_vec[:255])
            if torques:
                payload = sensor_codec.encode_torque(torques)
                packets.append(
                    signer.sign_packet(job_id, SensorChannel.TORQUE, ts_ns, payload),
                )

        if max_packets and len(packets) >= max_packets:
            break

    log.info("bridge_loader: loaded %d packets from %s", len(packets), pkl_path)
    return packets


def _find_key(d: dict[str, object], candidates: list[str]) -> str | None:
    """Return the first key from candidates that exists in d."""
    for k in candidates:
        if k in d:
            return k
    return None
