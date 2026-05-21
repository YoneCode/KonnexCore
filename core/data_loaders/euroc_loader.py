"""EuRoC MAV dataset loader.

Reads the ASL/EuRoC format:
  - mav0/imu0/data.csv → IMU SensorPackets (gyro + accel at 200 Hz)
  - mav0/cam0/data/ → CAMERA SensorPackets (grayscale 752×480)

CSV header: #timestamp [ns],w_RS_S_x [rad s^-1],...,a_RS_S_x [m s^-2],...

Reference: https://projects.asl.ethz.ch/datasets/doku.php?id=kmavvisualinertialdatasets
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from core import sensor_codec
from core.models import SensorChannel, SensorPacket
from rootid.sensor_signer import SensorSigner

log = logging.getLogger(__name__)


def load_imu_packets(
    dataset_dir: Path,
    *,
    signer: SensorSigner,
    job_id: str,
    max_packets: int | None = None,
) -> list[SensorPacket]:
    """Read mav0/imu0/data.csv and yield signed IMU SensorPackets.

    EuRoC IMU CSV columns (after the header comment):
        timestamp [ns], w_x, w_y, w_z, a_x, a_y, a_z
    """
    csv_path = dataset_dir / "mav0" / "imu0" / "data.csv"
    if not csv_path.exists():
        msg = f"imu0/data.csv not found in {dataset_dir}"
        raise FileNotFoundError(msg)

    packets: list[SensorPacket] = []
    with csv_path.open() as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.strip().split(",")
            if len(parts) != 7:  # noqa: PLR2004
                continue
            ts_ns = int(parts[0])
            gx, gy, gz = float(parts[1]), float(parts[2]), float(parts[3])
            ax, ay, az = float(parts[4]), float(parts[5]), float(parts[6])
            payload = sensor_codec.encode_imu(
                accel=(ax, ay, az),
                gyro=(gx, gy, gz),
            )
            packets.append(
                signer.sign_packet(job_id, SensorChannel.IMU, ts_ns, payload),
            )
            if max_packets and len(packets) >= max_packets:
                break

    log.info("euroc_loader: loaded %d IMU packets from %s", len(packets), csv_path)
    return packets


def load_cam_packets(
    dataset_dir: Path,
    *,
    signer: SensorSigner,
    job_id: str,
    max_packets: int | None = None,
    resize: tuple[int, int] = (64, 64),
) -> list[SensorPacket]:
    """Read mav0/cam0/data/ grayscale PNGs and yield signed CAMERA SensorPackets."""
    cam_dir = dataset_dir / "mav0" / "cam0" / "data"
    if not cam_dir.exists():
        msg = f"cam0/data/ not found in {dataset_dir}"
        raise FileNotFoundError(msg)

    from PIL import Image

    packets: list[SensorPacket] = []
    for png in sorted(cam_dir.glob("*.png")):
        ts_ns = int(png.stem)
        img = Image.open(png).convert("RGB").resize(resize, Image.Resampling.BILINEAR)
        arr = np.asarray(img, dtype=np.uint8)
        # Ensure (H, W, 3) shape.
        if arr.ndim == 2:  # noqa: PLR2004 — grayscale
            arr = np.stack([arr, arr, arr], axis=-1)
        payload = sensor_codec.encode_camera_frame(arr)
        packets.append(
            signer.sign_packet(job_id, SensorChannel.CAMERA, ts_ns, payload),
        )
        if max_packets and len(packets) >= max_packets:
            break

    log.info("euroc_loader: loaded %d cam packets from %s", len(packets), cam_dir)
    return packets
