"""Versioned byte codecs for camera, IMU, and torque sensor payloads.

These codecs are pure (no PyBullet, no I/O) so they can be exercised
in unit tests without the heavy simulator stack. Phase 3 (DetVerify
cross-modal stage) will use the matching ``decode_*`` functions to
recover sensor values from the canonical ``SensorPacket.data_b64``
field.

On-the-wire layout (all multi-byte integers big-endian)::

    camera   b"npy:v1\\x00" || H(u32) || W(u32) || C(u8) || dtype(1B) || raw
    imu      b"imu:v1\\x00" || ax,ay,az,gx,gy,gz (6× float32)
    torque   b"tor:v1\\x00" || n(u8) || tau_0..tau_{n-1} (n× float32)

``dtype`` for camera frames is ``b"u"`` (uint8) at present; the field
is reserved so a future float-pixel format can coexist.
"""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

CAMERA_MAGIC: bytes = b"npy:v1\x00"
IMU_MAGIC: bytes = b"imu:v1\x00"
TORQUE_MAGIC: bytes = b"tor:v1\x00"

_CAMERA_HEADER_LEN: int = len(CAMERA_MAGIC) + 4 + 4 + 1 + 1
_IMU_PAYLOAD_LEN: int = 6 * 4
_IMU_TOTAL_LEN: int = len(IMU_MAGIC) + _IMU_PAYLOAD_LEN
_TORQUE_HEADER_LEN: int = len(TORQUE_MAGIC) + 1
_MAX_JOINTS: int = 255
_CAMERA_NDIM: int = 3


# ---------------------------------------------------------------------------
# Camera frames
# ---------------------------------------------------------------------------


def encode_camera_frame(arr: NDArray[np.uint8]) -> bytes:
    """Encode a 3-D uint8 image array (H, W, C) into the camera codec format.

    Args:
        arr: Image array, ``ndim == 3`` and ``dtype == uint8``.

    Returns:
        Byte string per the format documented at module level.

    Raises:
        ValueError: On non-uint8 dtype, wrong rank, or too many channels.
    """
    if arr.dtype != np.uint8:
        msg = f"camera frame dtype must be uint8, got {arr.dtype!s}"
        raise ValueError(msg)
    if arr.ndim != _CAMERA_NDIM:
        msg = f"camera frame must be 3-D (H, W, C), got ndim={arr.ndim}"
        raise ValueError(msg)
    h, w, c = arr.shape
    if c > _MAX_JOINTS:
        msg = f"channel count must fit in u8 (<= {_MAX_JOINTS}), got {c}"
        raise ValueError(msg)
    return (
        CAMERA_MAGIC
        + h.to_bytes(4, "big")
        + w.to_bytes(4, "big")
        + bytes([c])
        + b"u"
        + arr.tobytes(order="C")
    )


def decode_camera_frame(data: bytes) -> NDArray[np.uint8]:
    """Decode a camera-codec byte string back into a numpy array.

    Raises:
        ValueError: If the magic prefix is wrong, the payload is
            truncated, or the dtype tag is unsupported.
    """
    if not data.startswith(CAMERA_MAGIC):
        msg = f"camera codec: bad magic, expected {CAMERA_MAGIC!r}"
        raise ValueError(msg)
    if len(data) < _CAMERA_HEADER_LEN:
        msg = "camera codec: header truncated"
        raise ValueError(msg)
    cursor = len(CAMERA_MAGIC)
    h = int.from_bytes(data[cursor : cursor + 4], "big")
    cursor += 4
    w = int.from_bytes(data[cursor : cursor + 4], "big")
    cursor += 4
    c = data[cursor]
    cursor += 1
    dtype_tag = data[cursor : cursor + 1]
    cursor += 1
    if dtype_tag != b"u":
        msg = f"camera codec: unsupported dtype tag {dtype_tag!r}"
        raise ValueError(msg)
    expected_payload = h * w * c
    if len(data) - cursor != expected_payload:
        msg = (
            f"camera codec: payload length mismatch "
            f"(header expects {expected_payload}, body has {len(data) - cursor})"
        )
        raise ValueError(msg)
    arr = np.frombuffer(data[cursor:], dtype=np.uint8).reshape(h, w, c)
    return arr.copy()  # detach from the original buffer for safety.


# ---------------------------------------------------------------------------
# IMU
# ---------------------------------------------------------------------------


def encode_imu(
    *,
    accel: tuple[float, float, float],
    gyro: tuple[float, float, float],
) -> bytes:
    """Encode IMU readings into the imu-codec format.

    Args:
        accel: Linear acceleration ``(ax, ay, az)`` in m/s².
        gyro: Angular velocity ``(gx, gy, gz)`` in rad/s.

    Returns:
        31-byte payload: 7 magic + 24 floats.
    """
    return IMU_MAGIC + struct.pack(">6f", *accel, *gyro)


def decode_imu(
    data: bytes,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Decode an IMU payload into ``(accel, gyro)`` triples.

    Raises:
        ValueError: On wrong magic or wrong total length.
    """
    if not data.startswith(IMU_MAGIC):
        msg = f"imu codec: bad magic, expected {IMU_MAGIC!r}"
        raise ValueError(msg)
    if len(data) != _IMU_TOTAL_LEN:
        msg = f"imu codec: payload length must be {_IMU_TOTAL_LEN}, got {len(data)}"
        raise ValueError(msg)
    fields = struct.unpack(">6f", data[len(IMU_MAGIC) :])
    return (fields[0], fields[1], fields[2]), (fields[3], fields[4], fields[5])


# ---------------------------------------------------------------------------
# Torque
# ---------------------------------------------------------------------------


def encode_torque(torques: tuple[float, ...]) -> bytes:
    """Encode per-joint applied torques (float32) into the torque-codec format.

    Args:
        torques: One float per joint. ``len(torques)`` must fit in u8.

    Returns:
        ``magic ‖ n(u8) ‖ tau_0..tau_{n-1}`` as 4n-byte float32 BE.

    Raises:
        ValueError: If ``torques`` is empty or longer than 255 entries.
    """
    n = len(torques)
    if n == 0:
        msg = "torque codec: torques must be non-empty"
        raise ValueError(msg)
    if n > _MAX_JOINTS:
        msg = f"torque codec: at most 255 joints, got {n}"
        raise ValueError(msg)
    return TORQUE_MAGIC + bytes([n]) + struct.pack(f">{n}f", *torques)


def decode_torque(data: bytes) -> tuple[float, ...]:
    """Decode a torque payload into a tuple of floats.

    Raises:
        ValueError: On wrong magic or truncated payload.
    """
    if not data.startswith(TORQUE_MAGIC):
        msg = f"torque codec: bad magic, expected {TORQUE_MAGIC!r}"
        raise ValueError(msg)
    if len(data) < _TORQUE_HEADER_LEN:
        msg = "torque codec: header truncated"
        raise ValueError(msg)
    cursor = len(TORQUE_MAGIC)
    n = data[cursor]
    cursor += 1
    expected_payload = 4 * n
    if len(data) - cursor != expected_payload:
        msg = (
            f"torque codec: payload length mismatch "
            f"(header expects {expected_payload}, body has {len(data) - cursor})"
        )
        raise ValueError(msg)
    return struct.unpack(f">{n}f", data[cursor:])
