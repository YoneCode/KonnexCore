"""Tests for ``core/sensor_codec.py``.

Pins the on-the-wire byte layout for camera/IMU/torque payloads so
Phase 3 (DetVerify cross-modal) can decode them deterministically.
"""

from __future__ import annotations

import struct

import numpy as np
import pytest
from hypothesis import given
from hypothesis import settings as hsettings
from hypothesis import strategies as st

from core import sensor_codec

# ---------------------------------------------------------------------------
# Camera codec
# ---------------------------------------------------------------------------


class TestCameraCodec:
    def test_magic_prefix(self) -> None:
        assert sensor_codec.CAMERA_MAGIC == b"npy:v1\x00"

    def test_round_trip_uint8_rgba(self) -> None:
        arr = np.zeros((4, 8, 4), dtype=np.uint8)
        arr[2, 3, 0] = 255
        encoded = sensor_codec.encode_camera_frame(arr)
        decoded = sensor_codec.decode_camera_frame(encoded)
        assert decoded.shape == arr.shape
        assert decoded.dtype == arr.dtype
        np.testing.assert_array_equal(decoded, arr)

    def test_format_exact_for_known_input(self) -> None:
        arr = np.array([[[1, 2, 3, 4]]], dtype=np.uint8)  # 1x1x4
        encoded = sensor_codec.encode_camera_frame(arr)
        expected = (
            b"npy:v1\x00"
            + (1).to_bytes(4, "big")  # height
            + (1).to_bytes(4, "big")  # width
            + bytes([4])  # channels
            + b"u"  # dtype tag for uint8
            + bytes([1, 2, 3, 4])
        )
        assert encoded == expected

    def test_decode_rejects_bad_magic(self) -> None:
        bad = b"png:v1\x00" + b"\x00" * 100
        with pytest.raises(ValueError, match="magic"):
            sensor_codec.decode_camera_frame(bad)

    def test_decode_rejects_truncated_payload(self) -> None:
        # Header says 4x4x4 (=64 bytes) but body has only 1.
        truncated = (
            b"npy:v1\x00"
            + (4).to_bytes(4, "big")
            + (4).to_bytes(4, "big")
            + bytes([4])
            + b"u"
            + b"\x00"
        )
        with pytest.raises(ValueError, match="payload"):
            sensor_codec.decode_camera_frame(truncated)

    def test_encode_rejects_non_uint8(self) -> None:
        arr = np.zeros((1, 1, 4), dtype=np.float32)
        with pytest.raises(ValueError, match="uint8"):
            # Deliberately passing a float32 array to verify runtime rejection.
            sensor_codec.encode_camera_frame(arr)  # type: ignore[arg-type]

    def test_encode_rejects_wrong_rank(self) -> None:
        arr = np.zeros((4,), dtype=np.uint8)
        with pytest.raises(ValueError, match="3-D"):
            sensor_codec.encode_camera_frame(arr)

    def test_encode_rejects_too_many_channels(self) -> None:
        arr = np.zeros((1, 1, 256), dtype=np.uint8)
        with pytest.raises(ValueError, match="u8"):
            sensor_codec.encode_camera_frame(arr)

    def test_decode_rejects_short_header(self) -> None:
        # Magic + a few bytes — shorter than the full header.
        bad = b"npy:v1\x00" + b"\x00" * 3
        with pytest.raises(ValueError, match="header"):
            sensor_codec.decode_camera_frame(bad)

    def test_decode_rejects_unsupported_dtype_tag(self) -> None:
        bad = (
            b"npy:v1\x00"
            + (1).to_bytes(4, "big")
            + (1).to_bytes(4, "big")
            + bytes([1])
            + b"f"  # unsupported (Phase 2 only ships uint8)
            + b"\x00"
        )
        with pytest.raises(ValueError, match="dtype"):
            sensor_codec.decode_camera_frame(bad)

    @given(
        h=st.integers(min_value=1, max_value=16),
        w=st.integers(min_value=1, max_value=16),
        c=st.integers(min_value=1, max_value=4),
    )
    @hsettings(max_examples=20, deadline=None)
    def test_round_trip_property(self, h: int, w: int, c: int) -> None:
        arr = np.random.default_rng(0).integers(0, 256, size=(h, w, c), dtype=np.uint8)
        decoded = sensor_codec.decode_camera_frame(sensor_codec.encode_camera_frame(arr))
        np.testing.assert_array_equal(decoded, arr)


# ---------------------------------------------------------------------------
# IMU codec
# ---------------------------------------------------------------------------


class TestImuCodec:
    def test_magic_prefix(self) -> None:
        assert sensor_codec.IMU_MAGIC == b"imu:v1\x00"

    def test_round_trip(self) -> None:
        accel = (1.5, -2.0, 9.81)
        gyro = (0.01, 0.02, -0.03)
        encoded = sensor_codec.encode_imu(accel=accel, gyro=gyro)
        decoded_accel, decoded_gyro = sensor_codec.decode_imu(encoded)
        for a, b in zip(accel, decoded_accel, strict=True):
            assert abs(a - b) < 1e-6
        for a, b in zip(gyro, decoded_gyro, strict=True):
            assert abs(a - b) < 1e-6

    def test_format_size(self) -> None:
        encoded = sensor_codec.encode_imu(accel=(0.0, 0.0, 0.0), gyro=(0.0, 0.0, 0.0))
        # 7 bytes magic + 6 * 4 bytes float32 = 31 bytes.
        assert len(encoded) == len(sensor_codec.IMU_MAGIC) + 6 * 4

    def test_format_exact_for_zero(self) -> None:
        encoded = sensor_codec.encode_imu(accel=(0.0, 0.0, 0.0), gyro=(0.0, 0.0, 0.0))
        expected = b"imu:v1\x00" + struct.pack(">6f", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        assert encoded == expected

    def test_decode_rejects_bad_magic(self) -> None:
        with pytest.raises(ValueError, match="magic"):
            sensor_codec.decode_imu(b"xyz:v1\x00" + b"\x00" * 24)

    def test_decode_rejects_wrong_length(self) -> None:
        with pytest.raises(ValueError, match="length"):
            sensor_codec.decode_imu(b"imu:v1\x00" + b"\x00" * 23)

    @given(
        accel=st.tuples(
            st.floats(allow_nan=False, allow_infinity=False, width=32),
            st.floats(allow_nan=False, allow_infinity=False, width=32),
            st.floats(allow_nan=False, allow_infinity=False, width=32),
        ),
        gyro=st.tuples(
            st.floats(allow_nan=False, allow_infinity=False, width=32),
            st.floats(allow_nan=False, allow_infinity=False, width=32),
            st.floats(allow_nan=False, allow_infinity=False, width=32),
        ),
    )
    @hsettings(max_examples=50, deadline=None)
    def test_round_trip_property(
        self,
        accel: tuple[float, float, float],
        gyro: tuple[float, float, float],
    ) -> None:
        encoded = sensor_codec.encode_imu(accel=accel, gyro=gyro)
        decoded_accel, decoded_gyro = sensor_codec.decode_imu(encoded)
        for a, b in zip(accel, decoded_accel, strict=True):
            # float32 round trip: bit-equal.
            assert struct.pack(">f", a) == struct.pack(">f", b)
        for a, b in zip(gyro, decoded_gyro, strict=True):
            assert struct.pack(">f", a) == struct.pack(">f", b)


# ---------------------------------------------------------------------------
# Torque codec
# ---------------------------------------------------------------------------


class TestTorqueCodec:
    def test_magic_prefix(self) -> None:
        assert sensor_codec.TORQUE_MAGIC == b"tor:v1\x00"

    def test_round_trip(self) -> None:
        torques = (1.0, -2.5, 3.14159, 0.0, 100.0)
        encoded = sensor_codec.encode_torque(torques)
        decoded = sensor_codec.decode_torque(encoded)
        assert len(decoded) == len(torques)
        for a, b in zip(torques, decoded, strict=True):
            assert abs(a - b) < 1e-5

    def test_format_exact_for_two_joints(self) -> None:
        encoded = sensor_codec.encode_torque((1.0, 2.0))
        expected = b"tor:v1\x00" + bytes([2]) + struct.pack(">2f", 1.0, 2.0)  # n
        assert encoded == expected

    def test_decode_rejects_bad_magic(self) -> None:
        with pytest.raises(ValueError, match="magic"):
            sensor_codec.decode_torque(b"xxx:v1\x00\x00")

    def test_decode_rejects_truncated(self) -> None:
        # Says n=3 but only 4 bytes follow.
        bad = b"tor:v1\x00" + bytes([3]) + b"\x00\x00\x00\x00"
        with pytest.raises(ValueError, match="payload"):
            sensor_codec.decode_torque(bad)

    def test_decode_rejects_short_header(self) -> None:
        # Magic only — no n byte.
        with pytest.raises(ValueError, match="header"):
            sensor_codec.decode_torque(b"tor:v1\x00")

    def test_encode_rejects_too_many_joints(self) -> None:
        with pytest.raises(ValueError, match="255"):
            sensor_codec.encode_torque(tuple([0.0] * 256))

    def test_encode_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            sensor_codec.encode_torque(())

    @given(
        torques=st.lists(
            st.floats(allow_nan=False, allow_infinity=False, width=32),
            min_size=1,
            max_size=32,
        ),
    )
    @hsettings(max_examples=50, deadline=None)
    def test_round_trip_property(self, torques: list[float]) -> None:
        encoded = sensor_codec.encode_torque(tuple(torques))
        decoded = sensor_codec.decode_torque(encoded)
        for a, b in zip(torques, decoded, strict=True):
            assert struct.pack(">f", a) == struct.pack(">f", b)
