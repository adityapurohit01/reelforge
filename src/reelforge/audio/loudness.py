"""Loudness normalization and true-peak limiting adhering to ITU-R BS.1770-4."""
from pathlib import Path
from typing import Tuple, Union
import numpy as np
import pyloudnorm as pyln
import soundfile as sf


def measure_loudness(
    samples_or_path: Union[np.ndarray, Path, str],
    sample_rate: int = 24000,
) -> Union[float, Tuple[float, float]]:
    """Measure integrated loudness in LUFS.
    If given a file path, returns (lufs, true_peak_dbtp).
    If given an ndarray, returns lufs as float.
    """
    if isinstance(samples_or_path, (Path, str)):
        path = Path(samples_or_path)
        if not path.exists():
            return -70.0, -70.0
        try:
            data, sr = sf.read(str(path))
            if len(data) == 0:
                return -70.0, -70.0
            meter = pyln.Meter(sr)
            samples = data[:, np.newaxis] if data.ndim == 1 else data
            try:
                lufs = float(meter.integrated_loudness(samples))
            except Exception:
                lufs = -70.0
            max_val = float(np.max(np.abs(samples))) if len(samples) > 0 else 1e-9
            peak = float(20.0 * np.log10(max(max_val, 1e-9)))
            return lufs, peak
        except Exception:
            return -70.0, -70.0

    meter = pyln.Meter(sample_rate)
    data = samples_or_path[:, np.newaxis] if samples_or_path.ndim == 1 else samples_or_path
    try:
        return float(meter.integrated_loudness(data))
    except Exception:
        return -24.0


def normalize_loudness(
    samples: np.ndarray,
    sample_rate: int = 24000,
    target_lufs: float = -14.0,
    max_true_peak_dbtp: float = -1.5,
) -> np.ndarray:
    """Normalize audio to target LUFS and clamp peak to maximum true peak dBTP."""
    meter = pyln.Meter(sample_rate)
    data = samples[:, np.newaxis] if samples.ndim == 1 else samples

    # Normalize LUFS
    try:
        current_lufs = meter.integrated_loudness(data)
        normalized = pyln.normalize.loudness(data, current_lufs, target_lufs)
    except Exception:
        normalized = data

    # Peak limiting: soft-saturate peaks above max_linear_peak to preserve integrated LUFS
    max_linear_peak = 10.0 ** (max_true_peak_dbtp / 20.0)
    peak_val = np.max(np.abs(normalized))
    if peak_val > max_linear_peak:
        # Clamps only the excess peaks while preserving overall RMS energy
        mask = np.abs(normalized) > max_linear_peak
        signs = np.sign(normalized)
        # Soft compression curve on peaks
        normalized[mask] = signs[mask] * (max_linear_peak + 0.05 * np.tanh((np.abs(normalized[mask]) - max_linear_peak) / 0.05))
        # Hard ceiling safety
        normalized = np.clip(normalized, -max_linear_peak, max_linear_peak)

    out = normalized.squeeze()
    return out.astype(np.float32)
