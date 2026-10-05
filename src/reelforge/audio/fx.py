"""Audio DSP effects for telephone acoustics and compression."""
import numpy as np
from scipy import signal


def apply_phone_effect(
    samples: np.ndarray,
    sample_rate: int = 24000,
    low_cutoff: float = 300.0,
    high_cutoff: float = 3400.0,
) -> np.ndarray:
    """Apply telephone band-pass filter (300-3400 Hz) and mild harmonic saturation to caller track."""
    nyquist = 0.5 * sample_rate
    low = low_cutoff / nyquist
    high = min(high_cutoff / nyquist, 0.99)

    # 4th-order Butterworth bandpass
    b, a = signal.butter(4, [low, high], btype="bandpass")
    filtered = signal.lfilter(b, a, samples)

    # Mild saturation/compression (soft clipping curve)
    compressed = np.tanh(filtered * 1.3) * 0.85
    return compressed.astype(np.float32)
