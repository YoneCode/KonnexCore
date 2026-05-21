"""TUM RGB-D dataset loader.

Reads the TUM RGB-D benchmark format:
  - accelerometer.txt → IMU SensorPackets
  - depth/*.png → CAMERA SensorPackets (encoded via sensor_codec)
  - groundtruth.txt → metadata (not emitted as packets; available for
    cross-modal verification in DetVerify Stage 3)

Reference: https://cvg.cit.tum.de/data/datasets/rgbd-dataset/file_formats
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from core import sensor_codec
from core.models import SensorChannel, SensorPacket
from rootid.sensor_signer import SensorSigner

log = logging.getLogger(__name__)

#: Seconds → nanoseconds.
_S_TO_NS: int = 1_000_000_000


def load_imu_packets(
    dataset_dir: Path,
    *,
    signer: SensorSigner,
    job_id: str,
    max_packets: int | None = None,
) -> list[SensorPacket]:
    """Read accelerometer.txt and yield signed IMU SensorPackets.

    The TUM accelerometer format is:
        # timestamp ax ay az
        1305031449.564825 -0.083818 7.244229 -6.657506

    We emit gyro as (0,0,0) because TUM freiburg1_desk doesn't ship a
    separate gyroscope file. DetVerify Stage 5 (anomaly) will still
    score the acceleration magnitudes.
    """
    accel_file = dataset_dir / "accelerometer.txt"
    if not accel_file.exists():
        msg = f"accelerometer.txt not found in {dataset_dir}"
        raise FileNotFoundError(msg)

    packets: list[SensorPacket] = []
    with accel_file.open() as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.strip().split()
            if len(parts) != 4:  # noqa: PLR2004
                continue
            ts_s = float(parts[0])
            ax, ay, az = float(parts[1]), float(parts[2]), float(parts[3])
            ts_ns = int(ts_s * _S_TO_NS)
            payload = sensor_codec.encode_imu(
                accel=(ax, ay, az),
                gyro=(0.0, 0.0, 0.0),
            )
            packets.append(
                signer.sign_packet(job_id, SensorChannel.IMU, ts_ns, payload),
            )
            if max_packets and len(packets) >= max_packets:
                break

    log.info("tum_loader: loaded %d IMU packets from %s", len(packets), accel_file)
    return packets


def load_depth_packets(
    dataset_dir: Path,
    *,
    signer: SensorSigner,
    job_id: str,
    max_packets: int | None = None,
    resize: tuple[int, int] = (64, 64),
) -> list[SensorPacket]:
    """Read depth PNGs and yield signed CAMERA SensorPackets.

    Depth images are 16-bit PNG (millimeters). We normalize to uint8
    (0-255 range mapped from the 0-10m range) and encode as a
    single-channel "camera" frame via sensor_codec.
    """
    depth_dir = dataset_dir / "depth"
    depth_txt = dataset_dir / "depth.txt"
    if not depth_dir.exists():
        msg = f"depth/ directory not found in {dataset_dir}"
        raise FileNotFoundError(msg)

    # Read the association file for timestamps.
    entries: list[tuple[float, Path]] = []
    if depth_txt.exists():
        with depth_txt.open() as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.strip().split()
                if len(parts) >= 2:  # noqa: PLR2004
                    ts_s = float(parts[0])
                    img_path = dataset_dir / parts[1]
                    if img_path.exists():
                        entries.append((ts_s, img_path))
    else:
        # Fallback: sort depth PNGs by filename (which is the timestamp).
        for png in sorted(depth_dir.glob("*.png")):
            ts_s = float(png.stem)
            entries.append((ts_s, png))

    from PIL import Image

    packets: list[SensorPacket] = []
    for ts_s, img_path in entries:
        ts_ns = int(ts_s * _S_TO_NS)
        img = Image.open(img_path)
        img_resized = img.resize(resize, Image.Resampling.NEAREST)
        arr = np.asarray(img_resized, dtype=np.uint16)
        # Normalize 16-bit depth (mm) to uint8 (0-255, capped at 10m).
        arr_norm = np.clip(arr / 10_000.0 * 255, 0, 255).astype(np.uint8)
        # Expand to 3-channel for sensor_codec compatibility (H, W, C).
        arr_3ch = np.stack([arr_norm, arr_norm, arr_norm], axis=-1)
        payload = sensor_codec.encode_camera_frame(arr_3ch)
        packets.append(
            signer.sign_packet(job_id, SensorChannel.CAMERA, ts_ns, payload),
        )
        if max_packets and len(packets) >= max_packets:
            break

    log.info("tum_loader: loaded %d depth packets from %s", len(packets), depth_dir)
    return packets
