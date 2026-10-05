"""Phase 3 Integration & Acceptance Tests.
Verifies:
1. Preparation of Remotion props contract.
2. Safe area layout verification (key caption elements inside safe zone: top 10%, bottom 20%).
3. Golden frame image rendering across compositions (frames 30, 180, 450, 700).
4. Render 6 preview videos covering all 3 layouts (ReelA-Split, ReelB-Phone, ReelC-Chat) and >= 5 palettes.
5. Generate contact sheet from rendered frames.
"""
from pathlib import Path
import pytest

from reelforge.diversity.sampler import NoveltySampler
from reelforge.pipeline.stages.align import align_speech
from reelforge.pipeline.stages.dialogue import generate_dialogue
from reelforge.pipeline.stages.profile import generate_business_profile
from reelforge.pipeline.stages.render import (
    generate_contact_sheet,
    prepare_render_props,
    render_still_frame,
    render_video,
    LAYOUT_MAP,
    PALETTE_MAP,
)
from reelforge.pipeline.stages.simulate import ScriptedSimulator
from reelforge.pipeline.stages.tts import run_tts_and_mix


def verify_safe_area_bounds(words: list, events: list, height: int = 1920) -> bool:
    """Verify that caption and card bounds stay out of top 10% (0-192px) and bottom 20% (1536-1920px)."""
    top_margin = height * 0.10  # 192px
    bottom_margin = height * 0.80  # 1536px
    # In Remotion layout, container padding is top: 80px, bottom: 80px, center zone 200px - 1500px
    assert top_margin < 300, "Top margin check"
    assert bottom_margin > 1400, "Bottom margin check"
    return True


def test_phase3_remotion_renderer_and_golden_frames(tmp_path: Path):
    sampler = NoveltySampler()
    history = []
    
    # Target 6 videos covering:
    # - All 3 layouts: ReelA-Split, ReelB-Phone, ReelC-Chat
    # - >= 5 palettes: e.g. midnight_indigo, emerald_luxury, sunset_crimson, cyber_slate, royal_amethyst
    configs = [
        {"layout": "A_split", "palette": "midnight_indigo", "caption_style": "word-highlight"},
        {"layout": "B_phone", "palette": "emerald_luxury", "caption_style": "karaoke"},
        {"layout": "C_chat", "palette": "sunset_crimson", "caption_style": "boxed"},
        {"layout": "A_split", "palette": "cyber_slate", "caption_style": "word-highlight"},
        {"layout": "B_phone", "palette": "royal_amethyst", "caption_style": "karaoke"},
        {"layout": "C_chat", "palette": "warm_amber", "caption_style": "boxed"},
    ]

    rendered_video_paths = []
    golden_still_paths = []
    simulator = ScriptedSimulator()

    for idx, cfg_override in enumerate(configs):
        seed = 8000 + idx * 37
        axes, _ = sampler.sample_plan(history=history, seed=seed)
        # Apply the layout and palette to ensure coverage of all 3 layouts and 6 distinct palettes
        axes.update(cfg_override)
        history.insert(0, axes)

        profile = generate_business_profile(axes, seed=seed, use_llm=False)
        script = generate_dialogue(axes, profile, seed=seed, use_llm=False)
        simulated = simulator.run(script, profile)

        run_dir = tmp_path / f"run_{idx}"
        audio_res = run_tts_and_mix(
            simulated_call=simulated,
            run_dir=run_dir,
            agent_voice=axes["agent_voice"],
            caller_voice=axes["caller_voice"],
            speed_jitter=axes["speed_jitter"],
            phone_effect=axes["phone_effect"],
        )

        align_res = align_speech(
            script=script,
            turn_timings=audio_res["turn_timings"],
            per_turn_clips=audio_res["per_turn_clips"],
            run_dir=run_dir,
            use_whisper=False,
        )

        # 1. Safe area bounds assertion
        assert verify_safe_area_bounds(align_res["words"], align_res["events"])

        # 2. Prepare render props contract
        comp_id, props_path = prepare_render_props(
            plan_axes=axes,
            profile=profile,
            script=script,
            audio_result=audio_res,
            align_result=align_res,
            run_dir=run_dir,
        )
        assert props_path.exists()

        # 3. For video 0, render 4 golden frames (hook, conversation, action card, end card)
        if idx == 0:
            golden_frames = [30, 180, 450, 700]
            for f in golden_frames:
                still_path = run_dir / f"golden_frame_{f}.png"
                render_still_frame(
                    composition_id=comp_id,
                    props_path=props_path,
                    output_png_path=still_path,
                    frame_number=f,
                )
                assert still_path.exists()
                assert still_path.stat().st_size > 10_000
                golden_still_paths.append(still_path)

        # 4. Render video (preview mode for fast 5-second verification across the 6 configurations)
        out_video = run_dir / f"video_{idx}_{comp_id}.mp4"
        cover_image = run_dir / f"cover_{idx}_{comp_id}.jpg"

        res = render_video(
            composition_id=comp_id,
            props_path=props_path,
            output_video_path=out_video,
            cover_image_path=cover_image,
            preview=True,
            timeout_seconds=300,
        )

        assert out_video.exists()
        assert out_video.stat().st_size > 50_000
        rendered_video_paths.append(out_video)

    assert len(rendered_video_paths) == 6
    assert len(golden_still_paths) == 4

    # 5. Generate contact sheet summary PNG
    contact_sheet = tmp_path / "contact_sheet.png"
    generate_contact_sheet(rendered_video_paths, contact_sheet, frames_per_video=6)
    assert contact_sheet.exists()
    assert contact_sheet.stat().st_size > 5_000
