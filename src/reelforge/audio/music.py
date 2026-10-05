"""CC0 Background music bed generator and sidechain ducking."""
from pathlib import Path
from typing import Optional
import numpy as np


def generate_ambient_music_bed(
    duration_s: float,
    sample_rate: int = 24000,
    bpm: float = 85.0,
    base_freq: float = 220.0,
) -> np.ndarray:
    """Procedurally synthesizes a pleasant, minimal LoFi/ambient pad chord progression.
    Guarantees royalty-free CC0 audio bed without external network dependency.
    """
    total_samples = int(duration_s * sample_rate)
    t = np.linspace(0, duration_s, total_samples, endpoint=False)

    # Chord progression: A minor -> F major -> C major -> G major
    # Frequencies (Hz): [220, 261.63, 329.63], [174.61, 220, 261.63], etc.
    chords = [
        [220.0, 261.63, 329.63],  # Am
        [174.61, 220.0, 261.63],  # F
        [261.63, 329.63, 392.0],  # C
        [196.0, 246.94, 293.66],  # G
    ]

    music = np.zeros(total_samples, dtype=np.float32)
    bar_dur = (60.0 / bpm) * 4  # 4 beats per bar

    for i, chord in enumerate(chords):
        t_start = i * bar_dur
        while t_start < duration_s:
            t_end = min(duration_s, t_start + bar_dur)
            idx_start = int(t_start * sample_rate)
            idx_end = int(t_end * sample_rate)
            chunk_t = t[idx_start:idx_end]

            # Warm harmonics with soft attack
            chunk_signal = np.zeros(len(chunk_t), dtype=np.float32)
            for freq in chord:
                chunk_signal += 0.3 * np.sin(2 * np.pi * freq * chunk_t)
                chunk_signal += 0.1 * np.sin(2 * np.pi * freq * 2.0 * chunk_t)

            # Soft attack and release envelope
            env = np.ones(len(chunk_t), dtype=np.float32)
            fade_len = int(0.2 * sample_rate)
            if len(env) > fade_len * 2:
                env[:fade_len] = np.linspace(0.1, 1.0, fade_len)
                env[-fade_len:] = np.linspace(1.0, 0.1, fade_len)

            music[idx_start:idx_end] += chunk_signal * env
            t_start += len(chords) * bar_dur

    # Normalize bed level to gentle background (-22 LUFS approx / max amp 0.15)
    max_amp = np.max(np.abs(music))
    if max_amp > 0:
        music = (music / max_amp) * 0.12

    return music.astype(np.float32)


def apply_sidechain_ducking(
    music: np.ndarray,
    speech_mask: np.ndarray,
    ducking_factor: float = 0.22,  # Attenuation during speech (-13 dB)
    smoothing_samples: int = 2400,  # ~100 ms smoothing
) -> np.ndarray:
    """Attenuate music during speech segments with smooth crossfade ramps."""
    length = min(len(music), len(speech_mask))
    gain = np.ones(length, dtype=np.float32)

    # Where speech is present, reduce gain
    gain[speech_mask[:length] > 0.05] = ducking_factor

    # Smooth the gain curve with a moving average box filter
    box = np.ones(smoothing_samples, dtype=np.float32) / smoothing_samples
    smoothed_gain = np.convolve(gain, box, mode="same")

    ducked = music[:length] * smoothed_gain
    return ducked.astype(np.float32)
