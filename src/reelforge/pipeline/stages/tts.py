"""Stage 5 TTS & Audio Mix for ReelForge.
Provides TTSProvider interface, KokoroTTS implementation, voice pairing,
micro-timing jitter, and audio mixing.
"""
from abc import ABC, abstractmethod
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import soundfile as sf

from reelforge.audio.mix import mix_call_audio
from reelforge.pipeline.stages.simulate import SimulatedCall

logger = logging.getLogger(__name__)


class TTSProvider(ABC):
    @abstractmethod
    def synthesize(self, text: str, voice: str, speed: float = 1.0) -> Tuple[np.ndarray, int]:
        """Synthesize text into raw float32 samples and sample rate."""
        pass


class KokoroTTS(TTSProvider):
    def __init__(self, model_path: str = "assets/kokoro/kokoro-v1.0.onnx", voices_path: str = "assets/kokoro/voices-v1.0.bin"):
        self.model_path = model_path
        self.voices_path = voices_path
        self._kokoro = None
        self._fallback = SyntheticTTS()

    def _get_engine(self):
        if self._kokoro is None:
            try:
                from kokoro_onnx import Kokoro
                self._kokoro = Kokoro(self.model_path, self.voices_path)
            except Exception as e:
                logger.warning(f"Kokoro initialization failed ({e}), falling back to SyntheticTTS")
                return None
        return self._kokoro

    def synthesize(self, text: str, voice: str, speed: float = 1.0) -> Tuple[np.ndarray, int]:
        engine = self._get_engine()
        if engine is not None:
            try:
                samples, sr = engine.create(text, voice=voice, speed=speed, lang="en-us")
                return samples.astype(np.float32), sr
            except Exception as e:
                logger.warning(f"Kokoro synthesis failed ({e}), using SyntheticTTS")
        return self._fallback.synthesize(text, voice=voice, speed=speed)


class SyntheticTTS(TTSProvider):
    """Fallback synthetic speech generator (generates formant modulated audio) for fast testing when TTS weights are loading."""

    def synthesize(self, text: str, voice: str, speed: float = 1.0) -> Tuple[np.ndarray, int]:
        sr = 24000
        words = text.split()
        dur = max(1.2, len(words) * (0.28 / speed))
        t = np.linspace(0, dur, int(dur * sr), endpoint=False)
        pitch = 180.0 if "f_" in voice else 125.0
        # Multi-harmonic voice simulation with natural cadence
        carrier = np.sin(2 * np.pi * pitch * t) + 0.3 * np.sin(2 * np.pi * pitch * 2 * t)
        env = 0.5 + 0.4 * np.sin(2 * np.pi * (len(words) / dur) * t)
        samples = (carrier * env * 0.4).astype(np.float32)
        return samples, sr


def run_tts_and_mix(
    simulated_call: SimulatedCall,
    run_dir: Path,
    agent_voice: str = "af_bella",
    caller_voice: str = "am_adam",
    speed_jitter: float = 0.0,
    phone_effect: bool = True,
    tts_provider: Optional[TTSProvider] = None,
) -> Dict[str, Any]:
    """Execute Stage 5: synthesize per-turn clips and produce mixed master track."""
    tts_dir = run_dir / "tts"
    tts_dir.mkdir(parents=True, exist_ok=True)

    if tts_provider is None:
        model_file = Path("assets/kokoro/kokoro-v1.0.onnx")
        voices_file = Path("assets/kokoro/voices-v1.0.bin")
        if model_file.exists() and voices_file.exists() and model_file.stat().st_size >= 300_000_000:
            try:
                with open(model_file, "rb") as f:
                    f.seek(0, 2)
                tts_provider = KokoroTTS(str(model_file), str(voices_file))
            except Exception:
                tts_provider = SyntheticTTS()
        else:
            tts_provider = SyntheticTTS()

    turn_clips = []
    per_turn_paths = []

    for i, turn in enumerate(simulated_call.turns):
        voice = agent_voice if turn.speaker == "agent" else caller_voice
        base_speed = 1.35
        speed = max(1.15, min(1.50, base_speed + speed_jitter))

        samples, sr = tts_provider.synthesize(turn.text, voice=voice, speed=speed)
        turn_wav = tts_dir / f"turn_{i}_{turn.speaker}.wav"
        sf.write(str(turn_wav), samples, sr)
        per_turn_paths.append(str(turn_wav))

        # Clamp pause between turns to 120ms max for crisp 22-38s spoken length
        clamped_pause = min(turn.pause_after_ms, 120)
        turn_clips.append((turn.speaker, samples, clamped_pause))

    master_wav_path = run_dir / "mix.wav"
    envelope_path = run_dir / "amplitude_envelope.json"

    mixed, lufs, envelope, turn_timings = mix_call_audio(
        turn_clips=turn_clips,
        sample_rate=24000,
        phone_effect_on_caller=phone_effect,
        target_lufs=-14.0,
        output_wav_path=master_wav_path,
        output_envelope_path=envelope_path,
    )

    total_dur_s = len(mixed) / 24000.0

    return {
        "master_wav_path": str(master_wav_path),
        "amplitude_envelope_path": str(envelope_path),
        "total_duration_seconds": round(total_dur_s, 2),
        "loudness_lufs": round(lufs, 2),
        "turn_timings": turn_timings,
        "per_turn_clips": per_turn_paths,
    }
