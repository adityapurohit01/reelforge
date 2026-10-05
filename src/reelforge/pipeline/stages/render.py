"""Stage 7: Remotion Video Renderer for ReelForge.
Prepares props.json with layout, theme tokens, word timestamps, amplitude envelope,
and coordinates subprocess execution of Remotion CLI for MP4 and cover frames.
"""
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

from reelforge.config import ReelForgeConfig, load_config
from reelforge.pipeline.stages.dialogue import DialogueScript
from reelforge.pipeline.stages.profile import BusinessProfile

logger = logging.getLogger(__name__)

# Remotion composition mapping
LAYOUT_MAP = {
    "A_split": "ReelA-Split",
    "B_phone": "ReelB-Phone",
    "C_chat": "ReelC-Chat",
    "A": "ReelA-Split",
    "B": "ReelB-Phone",
    "C": "ReelC-Chat",
}

# 12 Curated Palettes matching render/src/themes/palettes.ts
PALETTE_MAP = {
    "midnight_indigo": {
        "id": "midnight_indigo", "name": "Midnight Indigo",
        "background": "#0B0F19", "surface": "#151C2C",
        "primary": "#6366F1", "secondary": "#A855F7",
        "text": "#F8FAFC", "textSecondary": "#94A3B8",
        "agentWaveform": "#818CF8", "callerWaveform": "#38BDF8",
        "accent": "#10B981", "cardBg": "rgba(21, 28, 44, 0.85)", "border": "rgba(99, 102, 241, 0.25)",
    },
    "emerald_luxury": {
        "id": "emerald_luxury", "name": "Emerald Luxury",
        "background": "#051610", "surface": "#0D281E",
        "primary": "#10B981", "secondary": "#34D399",
        "text": "#ECFDF5", "textSecondary": "#A7F3D0",
        "agentWaveform": "#34D399", "callerWaveform": "#F59E0B",
        "accent": "#FBBF24", "cardBg": "rgba(13, 40, 30, 0.85)", "border": "rgba(16, 185, 129, 0.25)",
    },
    "sunset_crimson": {
        "id": "sunset_crimson", "name": "Sunset Crimson",
        "background": "#180B0E", "surface": "#2D1219",
        "primary": "#F43F5E", "secondary": "#FB923C",
        "text": "#FFF1F2", "textSecondary": "#FECDD3",
        "agentWaveform": "#FB7185", "callerWaveform": "#FBBF24",
        "accent": "#E11D48", "cardBg": "rgba(45, 18, 25, 0.85)", "border": "rgba(244, 63, 94, 0.25)",
    },
    "cyber_slate": {
        "id": "cyber_slate", "name": "Cyber Slate",
        "background": "#0F172A", "surface": "#1E293B",
        "primary": "#38BDF8", "secondary": "#818CF8",
        "text": "#F1F5F9", "textSecondary": "#94A3B8",
        "agentWaveform": "#38BDF8", "callerWaveform": "#4ADE80",
        "accent": "#06B6D4", "cardBg": "rgba(30, 41, 59, 0.85)", "border": "rgba(56, 189, 248, 0.25)",
    },
    "royal_amethyst": {
        "id": "royal_amethyst", "name": "Royal Amethyst",
        "background": "#120B1C", "surface": "#211432",
        "primary": "#A855F7", "secondary": "#EC4899",
        "text": "#FAF5FF", "textSecondary": "#E9D5FF",
        "agentWaveform": "#C084FC", "callerWaveform": "#38BDF8",
        "accent": "#F472B6", "cardBg": "rgba(33, 20, 50, 0.85)", "border": "rgba(168, 85, 247, 0.25)",
    },
    "warm_amber": {
        "id": "warm_amber", "name": "Warm Amber",
        "background": "#1A1207", "surface": "#2E200C",
        "primary": "#F59E0B", "secondary": "#EA580C",
        "text": "#FEF3C7", "textSecondary": "#FDE68A",
        "agentWaveform": "#FBBF24", "callerWaveform": "#60A5FA",
        "accent": "#D97706", "cardBg": "rgba(46, 32, 12, 0.85)", "border": "rgba(245, 158, 11, 0.25)",
    },
    "oceanic_teal": {
        "id": "oceanic_teal", "name": "Oceanic Teal",
        "background": "#061A1D", "surface": "#0C2E33",
        "primary": "#14B8A6", "secondary": "#06B6D4",
        "text": "#F0FDFA", "textSecondary": "#99F6E4",
        "agentWaveform": "#2DD4BF", "callerWaveform": "#F472B6",
        "accent": "#0D9488", "cardBg": "rgba(12, 46, 51, 0.85)", "border": "rgba(20, 184, 166, 0.25)",
    },
    "monochrome_stealth": {
        "id": "monochrome_stealth", "name": "Monochrome Stealth",
        "background": "#121212", "surface": "#1E1E1E",
        "primary": "#E2E8F0", "secondary": "#94A3B8",
        "text": "#FFFFFF", "textSecondary": "#A1A1AA",
        "agentWaveform": "#E2E8F0", "callerWaveform": "#38BDF8",
        "accent": "#64748B", "cardBg": "rgba(30, 30, 30, 0.9)", "border": "rgba(255, 255, 255, 0.15)",
    },
    "copper_bronze": {
        "id": "copper_bronze", "name": "Copper Bronze",
        "background": "#18100C", "surface": "#2D1D16",
        "primary": "#FB923C", "secondary": "#D97706",
        "text": "#FFF7ED", "textSecondary": "#FED7AA",
        "agentWaveform": "#FDBA74", "callerWaveform": "#34D399",
        "accent": "#C2410C", "cardBg": "rgba(45, 29, 22, 0.85)", "border": "rgba(251, 146, 60, 0.25)",
    },
    "nordic_frost": {
        "id": "nordic_frost", "name": "Nordic Frost",
        "background": "#0A1118", "surface": "#12202E",
        "primary": "#7DD3FC", "secondary": "#93C5FD",
        "text": "#F0F9FF", "textSecondary": "#BAE6FD",
        "agentWaveform": "#38BDF8", "callerWaveform": "#A78BFA",
        "accent": "#0284C7", "cardBg": "rgba(18, 32, 46, 0.85)", "border": "rgba(125, 211, 252, 0.25)",
    },
    "deep_plum": {
        "id": "deep_plum", "name": "Deep Plum",
        "background": "#160A1A", "surface": "#291330",
        "primary": "#D946EF", "secondary": "#EC4899",
        "text": "#FDF4FF", "textSecondary": "#F5D0FE",
        "agentWaveform": "#E879F9", "callerWaveform": "#22D3EE",
        "accent": "#C026D3", "cardBg": "rgba(41, 19, 48, 0.85)", "border": "rgba(217, 70, 239, 0.25)",
    },
    "forest_sage": {
        "id": "forest_sage", "name": "Forest Sage",
        "background": "#0B140E", "surface": "#16281C",
        "primary": "#84CC16", "secondary": "#22C55E",
        "text": "#F7FEE7", "textSecondary": "#D9F99D",
        "agentWaveform": "#A3E635", "callerWaveform": "#F59E0B",
        "accent": "#65A30D", "cardBg": "rgba(22, 40, 28, 0.85)", "border": "rgba(132, 204, 22, 0.25)",
    },
}


def prepare_render_props(
    plan_axes: Dict[str, Any],
    profile: BusinessProfile,
    script: DialogueScript,
    audio_result: Dict[str, Any],
    align_result: Dict[str, Any],
    run_dir: Path,
    config: Optional[ReelForgeConfig] = None,
) -> Tuple[str, Path]:
    """Assemble props.json contract for Remotion renderer and return (composition_id, props_path)."""
    cfg = config or load_config()

    layout_key = plan_axes.get("layout", "A_split")
    comp_id = LAYOUT_MAP.get(layout_key, "ReelA-Split")

    palette_key = plan_axes.get("palette", "midnight_indigo")
    palette = PALETTE_MAP.get(palette_key, PALETTE_MAP["midnight_indigo"])

    caption_style = plan_axes.get("caption_style", "word-highlight")

    # Load amplitude envelope
    env_file = Path(audio_result["amplitude_envelope_path"])
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            amplitude_envelope = json.load(f)
    else:
        amplitude_envelope = [0.2] * int(audio_result["total_duration_seconds"] * 30)

    # Stage master audio file inside render/public/audio for Remotion staticFile serving
    master_audio = Path(audio_result["master_wav_path"]).resolve()
    public_audio_dir = Path("render/public/audio")
    public_audio_dir.mkdir(parents=True, exist_ok=True)
    
    unique_audio_name = f"call_{run_dir.name}_{int(time.time() * 1000) % 1000000}.wav"
    staged_audio_path = public_audio_dir / unique_audio_name
    if master_audio.exists():
        shutil.copy(master_audio, staged_audio_path)
        audio_rel_url = f"audio/{unique_audio_name}"
    else:
        audio_rel_url = ""

    props_payload = {
        "business": {
            "name": profile.name,
            "vertical": profile.vertical,
            "city": profile.city,
            "owner_name": profile.owner_first_name,
        },
        "hook_text": script.hook_text,
        "audio_url": audio_rel_url,
        "total_duration_seconds": audio_result["total_duration_seconds"],
        "palette": palette,
        "caption_style": caption_style,
        "words": align_result["words"],
        "events": align_result["events"],
        "amplitude_envelope": amplitude_envelope,
        "owner_notification": script.owner_notification.model_dump(),
        "product": {
            "name": cfg.product.name,
            "tagline": cfg.product.tagline,
            "cta_url": cfg.product.cta_url,
            "cta_handle": cfg.product.cta_handle,
        },
    }

    render_dir = run_dir / "render"
    render_dir.mkdir(parents=True, exist_ok=True)
    props_path = render_dir / "props.json"

    with open(props_path, "w", encoding="utf-8") as f:
        json.dump(props_payload, f, indent=2)

    return comp_id, props_path


def render_video(
    composition_id: str,
    props_path: Path,
    output_video_path: Path,
    cover_image_path: Optional[Path] = None,
    preview: bool = False,
    remotion_dir: Path = Path("render"),
    timeout_seconds: int = 400,
) -> Dict[str, Any]:
    """Invoke Remotion CLI via subprocess to produce 1080x1920 MP4 and cover still."""
    output_video_path.parent.mkdir(parents=True, exist_ok=True)
    props_abs = props_path.resolve()
    out_video_abs = output_video_path.resolve()

    # Remotion render command
    # On Windows, npm/npx can be called via npx.cmd
    npx_cmd = shutil.which("npx") or "npx"

    cmd = [
        npx_cmd,
        "remotion",
        "render",
        composition_id,
        str(out_video_abs),
        f"--props={str(props_abs)}",
    ]

    if preview:
        cmd.extend(["--frames=0-150", "--scale=0.5"])

    start_time = time.time()
    logger.info(f"Starting Remotion render for {composition_id} -> {output_video_path.name}")
    
    proc = subprocess.run(
        cmd,
        cwd=str(remotion_dir),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        shell=True if os.name == "nt" else False,
    )

    elapsed = time.time() - start_time

    if proc.returncode != 0:
        error_msg = f"Remotion render failed (code {proc.returncode}):\n{proc.stderr}\n{proc.stdout}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    # Generate cover still at frame 35 (peak hook presence)
    if cover_image_path:
        cover_image_path.parent.mkdir(parents=True, exist_ok=True)
        cover_abs = cover_image_path.resolve()
        cover_cmd = [
            npx_cmd,
            "remotion",
            "still",
            composition_id,
            str(cover_abs),
            "--frame=35",
            f"--props={str(props_abs)}",
        ]
        subprocess.run(
            cover_cmd,
            cwd=str(remotion_dir),
            capture_output=True,
            timeout=120,
            shell=True if os.name == "nt" else False,
        )

    return {
        "video_path": str(output_video_path),
        "cover_path": str(cover_image_path) if cover_image_path else None,
        "composition_id": composition_id,
        "render_time_seconds": round(elapsed, 2),
        "file_size_mb": round(output_video_path.stat().st_size / (1024 * 1024), 2) if output_video_path.exists() else 0.0,
    }


def render_still_frame(
    composition_id: str,
    props_path: Path,
    output_png_path: Path,
    frame_number: int = 30,
    remotion_dir: Path = Path("render"),
) -> Path:
    """Render a single still frame at a given frame number for golden-image testing."""
    output_png_path.parent.mkdir(parents=True, exist_ok=True)
    npx_cmd = shutil.which("npx") or "npx"

    cmd = [
        npx_cmd,
        "remotion",
        "still",
        composition_id,
        str(output_png_path.resolve()),
        f"--frame={frame_number}",
        f"--props={str(props_path.resolve())}",
    ]

    subprocess.run(
        cmd,
        cwd=str(remotion_dir),
        check=True,
        capture_output=True,
        shell=True if os.name == "nt" else False,
    )
    return output_png_path


def generate_contact_sheet(
    video_paths: List[Path],
    output_png: Path,
    frames_per_video: int = 6,
) -> Path:
    """Generate a contact sheet tile PNG of the rendered videos using FFmpeg."""
    output_png.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = output_png.parent / "contact_thumbs"
    temp_dir.mkdir(parents=True, exist_ok=True)

    thumb_paths = []
    ffmpeg_cmd = shutil.which("ffmpeg") or "ffmpeg"

    for v_idx, v_path in enumerate(video_paths):
        for f_idx in range(frames_per_video):
            # Sample frames at 15%, 30%, 45%, 60%, 75%, 90% through video
            pos_ratio = (f_idx + 1) / (frames_per_video + 1)
            thumb_file = temp_dir / f"v_{v_idx}_f_{f_idx}.jpg"
            # Get video duration or sample roughly at seconds
            ss = round(2.0 + pos_ratio * 20.0, 1)
            subprocess.run(
                [
                    ffmpeg_cmd, "-y", "-ss", str(ss), "-i", str(v_path),
                    "-vframes", "1", "-vf", "scale=270:480", str(thumb_file)
                ],
                capture_output=True,
                check=False,
            )
            if thumb_file.exists():
                thumb_paths.append(thumb_file)

    # Tile images together
    if thumb_paths:
        tile_w = frames_per_video
        tile_h = len(video_paths)
        pattern = str(temp_dir / "v_%d_f_%d.jpg")
        # Direct stitch with ffmpeg or fallback tile
        tile_cmd = [
            ffmpeg_cmd, "-y",
            "-pattern_type", "glob", "-i", f"{str(temp_dir)}/*.jpg",
            "-filter_complex", f"tile={tile_w}x{tile_h}",
            str(output_png)
        ]
        res = subprocess.run(tile_cmd, capture_output=True)
        if res.returncode != 0 or not output_png.exists():
            # Fallback simple concat or copy first thumbnail
            shutil.copy(thumb_paths[0], output_png)

    return output_png
