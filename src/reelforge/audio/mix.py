"""Audio track mixing, pause scheduling, ducking, and amplitude envelope extraction."""
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import soundfile as sf

from reelforge.audio.fx import apply_phone_effect
from reelforge.audio.loudness import measure_loudness, normalize_loudness
from reelforge.audio.music import apply_sidechain_ducking, generate_ambient_music_bed


def extract_amplitude_envelope(
    samples: np.ndarray,
    sample_rate: int = 24000,
    fps: int = 30,
) -> List[float]:
    """Extract per-frame RMS amplitude envelope at target fps, smoothed and normalized [0, 1]."""
    samples_per_frame = sample_rate / fps
    total_frames = int(np.ceil(len(samples) / samples_per_frame))
    envelope = []

    for f in range(total_frames):
        start_idx = int(f * samples_per_frame)
        end_idx = min(len(samples), int((f + 1) * samples_per_frame))
        if start_idx >= len(samples):
            envelope.append(0.05)
            continue
        chunk = samples[start_idx:end_idx]
        rms = np.sqrt(np.mean(chunk**2)) if len(chunk) > 0 else 0.0
        envelope.append(float(rms))

    # Normalize to [0, 1] range with soft compression
    env_arr = np.array(envelope, dtype=np.float32)
    max_val = np.percentile(env_arr, 95) if len(env_arr) > 0 else 1.0
    if max_val > 0:
        normalized = np.clip(env_arr / max_val, 0.0, 1.0)
    else:
        normalized = np.full_like(env_arr, 0.05)

    return [round(float(v), 3) for v in normalized]


def mix_call_audio(
    turn_clips: List[Tuple[str, np.ndarray, int]],  # [(speaker, samples, pause_after_ms)]
    sample_rate: int = 24000,
    phone_effect_on_caller: bool = True,
    target_lufs: float = -14.0,
    output_wav_path: Optional[Path] = None,
    output_envelope_path: Optional[Path] = None,
) -> Tuple[np.ndarray, float, List[float], List[Dict[str, float]]]:
    """Assemble speech turns with pause scheduling, caller phone acoustics,
    ducked background music, and LUFS normalization.
    Returns: (mixed_samples, final_lufs, amplitude_envelope, turn_timings).
    """
    turn_timings = []
    speech_track_list = []
    speech_mask_list = []

    # Reel hook starts fast: initial silence <= 0.15s (approx 100ms)
    initial_pause_samples = int(0.10 * sample_rate)
    speech_track_list.append(np.zeros(initial_pause_samples, dtype=np.float32))
    speech_mask_list.append(np.zeros(initial_pause_samples, dtype=np.float32))
    current_time_s = 0.10

    for i, (speaker, samples, pause_ms) in enumerate(turn_clips):
        processed_samples = samples.copy()
        if speaker == "caller" and phone_effect_on_caller:
            processed_samples = apply_phone_effect(processed_samples, sample_rate=sample_rate)

        turn_dur = len(processed_samples) / sample_rate
        turn_start = current_time_s
        turn_end = turn_start + turn_dur
        turn_timings.append({
            "turn_index": i,
            "speaker": speaker,
            "start": round(turn_start, 3),
            "end": round(turn_end, 3),
        })

        speech_track_list.append(processed_samples)
        speech_mask_list.append(np.ones(len(processed_samples), dtype=np.float32))

        # Add pause after turn
        pause_samples = int((pause_ms / 1000.0) * sample_rate)
        speech_track_list.append(np.zeros(pause_samples, dtype=np.float32))
        speech_mask_list.append(np.zeros(pause_samples, dtype=np.float32))

        current_time_s = turn_end + (pause_ms / 1000.0)

    # Concatenate speech track
    full_speech = np.concatenate(speech_track_list)
    full_mask = np.concatenate(speech_mask_list)
    total_duration_s = len(full_speech) / sample_rate

    # Generate and duck CC0 background music bed
    music_bed = generate_ambient_music_bed(total_duration_s, sample_rate=sample_rate)
    ducked_music = apply_sidechain_ducking(music_bed, full_mask)

    # Combine speech and ducked music with exact length matching
    min_len = min(len(full_speech), len(ducked_music))
    mixed = full_speech[:min_len] + ducked_music[:min_len]

    # Final LUFS normalization (-14 +/- 1.5 LUFS) and peak limiting (< -1.5 dBTP)
    normalized = normalize_loudness(
        mixed,
        sample_rate=sample_rate,
        target_lufs=target_lufs,
        max_true_peak_dbtp=-1.6,
    )
    final_lufs = measure_loudness(normalized, sample_rate=sample_rate)

    # Extract 30 fps amplitude envelope
    envelope = extract_amplitude_envelope(normalized, sample_rate=sample_rate, fps=30)

    # Persist if paths provided
    if output_wav_path:
        output_wav_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_wav_path), normalized, sample_rate)

    if output_envelope_path:
        output_envelope_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_envelope_path, "w", encoding="utf-8") as f:
            json.dump(envelope, f)

    return normalized, final_lufs, envelope, turn_timings
