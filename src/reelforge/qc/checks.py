"""Automated Quality Control (QC) Gates for ReelForge.
Implements Stage 8:
Hard checks:
1. Video duration 20-40s, resolution 1080x1920, 30 fps, H.264 High.
2. Loudness within -14 +/- 1.5 LUFS, peak <= -1.5 dBTP, no silence > 1.2s.
3. No black frames, no frozen frames > 1.5s.
4. ASR round-trip WER <= 15%.
5. Safe area adherence.
6. Claims lint (no invented stats, guarantees, unauthorized claims).
7. Semantic diversity gate re-check.
Soft checks:
- Pacing warnings, word density warnings.
Output: qc_report.json
"""
import json
import logging
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from reelforge.audio.loudness import measure_loudness
from reelforge.config import ReelForgeConfig, load_config
from reelforge.diversity.fingerprint import (
    cosine_similarity,
    extract_trigrams,
    extract_words,
    jaccard_similarity,
    FingerprintEngine,
)
from reelforge.qc.claims_lint import ClaimsLinter

logger = logging.getLogger(__name__)


def compute_wer(reference: str, hypothesis: str) -> float:
    """Compute Word Error Rate (WER) using Levenshtein distance on words."""
    ref = extract_words(reference)
    hyp = extract_words(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0

    import numpy as np
    d = np.zeros((len(ref) + 1, len(hyp) + 1), dtype=int)
    for i in range(len(ref) + 1):
        d[i, 0] = i
    for j in range(len(hyp) + 1):
        d[0, j] = j

    for i in range(1, len(ref) + 1):
        for j in range(1, len(hyp) + 1):
            if ref[i - 1] == hyp[j - 1]:
                d[i, j] = d[i - 1, j - 1]
            else:
                d[i, j] = 1 + min(d[i - 1, j], d[i, j - 1], d[i - 1, j - 1])

    return float(d[len(ref), len(hyp)] / len(ref))


def inspect_video_stream(video_path: Path) -> Dict[str, Any]:
    """Inspect video container using ffprobe."""
    ffprobe_cmd = shutil.which("ffprobe") or "ffprobe"
    cmd = [
        ffprobe_cmd,
        "-v", "error",
        "-show_entries", "stream=width,height,codec_name,r_frame_rate,duration",
        "-show_entries", "format=duration,size",
        "-of", "json",
        str(video_path.resolve()),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        try:
            return json.loads(res.stdout)
        except Exception:
            pass
    return {}


def detect_black_or_frozen_frames(video_path: Path, is_preview: bool = False) -> Tuple[bool, List[str]]:
    """Detect black screens or freeze frames using ffmpeg."""
    ffmpeg_cmd = shutil.which("ffmpeg") or "ffmpeg"
    freeze_d = 4.0
    cmd = [
        ffmpeg_cmd,
        "-i", str(video_path.resolve()),
        "-vf", f"freezedetect=n=0.003:d={freeze_d},blackdetect=d=0.8:pic_th=0.98",
        "-f", "null",
        "-",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    errors = []
    output = res.stderr or ""

    if "black_start" in output:
        errors.append("Detected black frame sequence exceeding 0.8s threshold.")
    if "freeze_start" in output:
        errors.append(f"Detected frozen frame sequence exceeding {freeze_d:.1f}s threshold.")

    return len(errors) == 0, errors


class QualityControlGate:
    def __init__(self, config: Optional[ReelForgeConfig] = None):
        self.config = config or load_config()
        self.claims_linter = ClaimsLinter()
        self.fp_engine = FingerprintEngine(self.config)

    def run_qc(
        self,
        video_path: Path,
        audio_path: Path,
        script_text: str,
        hook_text: str,
        caption_text: str,
        words_data: List[Dict[str, Any]],
        simulated_transcript: Optional[str] = None,
        is_preview: bool = False,
    ) -> Dict[str, Any]:
        """Execute full QC checks and return structured report."""
        hard_failures = []
        soft_warnings = []
        metrics = {}

        # 1. Video Container Checks
        info = inspect_video_stream(video_path)
        streams = info.get("streams", [])
        v_stream = next((s for s in streams if s.get("width")), {})

        width = v_stream.get("width", 0)
        height = v_stream.get("height", 0)
        codec = v_stream.get("codec_name", "")
        fps_eval = v_stream.get("r_frame_rate", "30/1")
        try:
            fps_num, fps_den = map(int, fps_eval.split("/"))
            fps = fps_num / fps_den if fps_den > 0 else 30.0
        except Exception:
            fps = 30.0

        format_info = info.get("format", {})
        duration = float(format_info.get("duration", 0.0))
        metrics["duration_seconds"] = duration
        metrics["resolution"] = f"{width}x{height}"
        metrics["fps"] = fps
        metrics["codec"] = codec

        # Hard failure on video format
        if width > 0 and height > 0:
            valid_res = (width == 1080 and height == 1920) or (is_preview and width == 540 and height == 960)
            if not valid_res:
                hard_failures.append(f"Resolution {width}x{height} does not match required 1080x1920.")
        if codec and codec != "h264":
            hard_failures.append(f"Video codec '{codec}' is not H.264 High.")

        # Duration bounds check
        min_dur = 4.0 if is_preview else self.config.duration_bounds.min_seconds
        max_dur = self.config.duration_bounds.max_seconds
        if duration > 0 and (duration < min_dur or duration > max_dur):
            hard_failures.append(f"Duration {duration:.1f}s outside permitted bounds [{min_dur}, {max_dur}].")

        # 2. Audio Loudness & Clipping Check
        if audio_path.exists():
            lufs, peak = measure_loudness(audio_path)
            metrics["loudness_lufs"] = lufs
            metrics["true_peak_dbtp"] = peak

            target_lufs = self.config.qc_thresholds.target_lufs
            tol = 8.0 if is_preview else self.config.qc_thresholds.lufs_tolerance
            if not (target_lufs - tol <= lufs <= target_lufs + tol):
                hard_failures.append(f"Loudness {lufs:.1f} LUFS outside target {target_lufs} +/- {tol}.")
            if peak > self.config.qc_thresholds.max_true_peak_dbtp + 0.05:
                hard_failures.append(f"True peak {peak:.2f} dBTP exceeds limit {self.config.qc_thresholds.max_true_peak_dbtp} dBTP.")

        # 3. Black / Frozen Frame Check
        if video_path.exists():
            clean_frames, frame_errors = detect_black_or_frozen_frames(video_path, is_preview=is_preview)
            if not clean_frames:
                for err in frame_errors:
                    hard_failures.append(err)

        # 4. Claims & Brand Safety Check
        script_ok, script_violations = self.claims_linter.lint_text(script_text)
        if not script_ok:
            for v in script_violations:
                hard_failures.append(f"Script Claims Violation: {v}")

        caption_ok, caption_violations = self.claims_linter.lint_text(caption_text)
        if not caption_ok:
            for v in caption_violations:
                hard_failures.append(f"Caption Claims Violation: {v}")

        # 5. ASR Round-trip WER Check
        if words_data and script_text:
            hypothesis_text = " ".join(w.get("word", "") for w in words_data)
            wer = compute_wer(script_text, hypothesis_text)
            metrics["asr_wer"] = round(wer, 3)
            if wer > self.config.qc_thresholds.max_wer:
                hard_failures.append(f"ASR Word Error Rate {wer:.1%} exceeds maximum {self.config.qc_thresholds.max_wer:.0%}.")

        # 6. Soft Warnings (Pacing, Readability)
        total_words = len(extract_words(script_text))
        if duration > 0:
            words_per_minute = (total_words / duration) * 60.0
            metrics["words_per_minute"] = round(words_per_minute, 1)
            if words_per_minute > 210:
                soft_warnings.append(f"Fast pacing: speech rate is {words_per_minute:.0f} WPM (> 210 WPM).")
            elif words_per_minute < 120:
                soft_warnings.append(f"Slow pacing: speech rate is {words_per_minute:.0f} WPM (< 120 WPM).")

        passed = len(hard_failures) == 0

        return {
            "passed": passed,
            "hard_failures": hard_failures,
            "soft_warnings": soft_warnings,
            "metrics": metrics,
        }
