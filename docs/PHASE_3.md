# Phase 3 Documentation: Remotion Video Renderer, Layouts & Themes

## 1. What Was Built

Phase 3 implements the video composition and visual generation stage of **ReelForge**, utilizing **Remotion v4** (React + TypeScript) driven by a strictly typed contract via `props.json` and executed via the Remotion CLI with Chrome Headless Shell on CPU.

### A. Three Structurally Distinct Layouts
Unlike simple CSS recoloring, the three compositions are built with distinct UI paradigms:
1. **`ReelA-Split` (`render/src/compositions/ReelA_Split.tsx`)**:
   - Split layout with top business banner, vertical badge, and dynamic caller mood indicator.
   - Dynamic animated audio waveform driven by 30 fps RMS amplitude envelope (`Waveform.tsx`), color-coded per speaker.
   - Safe-area aware word-by-word captions (`Captions.tsx`) supporting word-highlight, karaoke, and boxed styling.
   - Action chips rail (`ActionChips.tsx`) animating tool calls ("Checked calendar", "Slot found", "Booked") in sync with script events.
   - Messenger-style owner notification card (`NotificationCard.tsx`) sliding in with call summary and next steps.
   - Opening hook card (0-2.5s) with kinetic motion and vertical motif pattern, and closing end card (last 2-3s) with brand CTA and product handle.
   - Persistent compliance footer: `"Simulated call • Fictional business"`.
2. **`ReelB-Phone` (`render/src/compositions/ReelB_Phone.tsx`)**:
   - Stylized smartphone call screen with business header, caller status, and live call timer (`00:14`).
   - Central caller avatar with animated pulsing rings responsive to voice volume.
   - Dual-channel live waveform and floating live captions.
   - Floating system notification popup for the owner message.
3. **`ReelC-Chat` (`render/src/compositions/ReelC_Chat.tsx`)**:
   - Dark modern messenger / live transcription chat feed.
   - Alternating agent and caller chat bubbles with timestamps, speaker badges, and live word-level highlight.
   - In-feed event cards showing appointment confirmations and tool execution results.

### B. Theme Engine & Safe-Area Constraints
- **Curated Palettes (`render/src/themes/palettes.ts`)**: 12 curated palettes (`midnight_indigo`, `emerald_luxury`, `sunset_crimson`, `cyber_slate`, `royal_amethyst`, `warm_amber`, `nordic_frost`, `rose_gold`, `oceanic_depths`, `crimson_minimal`, `electric_violet`, `coffee_caramel`) with deterministic hue jitter preserving WCAG AA contrast.
- **Typography & Motion (`render/src/themes/fonts.ts`, `motion.ts`)**: Modern font pairings (Inter, Outfit, Plus Jakarta Sans, DM Sans) and spring/cubic motion profiles.
- **Instagram Safe Areas**: Hard constraint enforced keeping captions, cards, and critical text strictly out of top 10% (0-192px) and bottom 20% (1536-1920px) where Instagram Reels UI elements (header, username, caption, sound, interaction icons) overlay.

### C. Python Orchestration & Subprocess Bridge (`src/reelforge/pipeline/stages/render.py`)
- `prepare_render_props()`: Bridges SQLite models, audio amplitude envelope, script events, and word timestamps into Remotion-compatible JSON. Audio files are staged into `render/public/audio/` so Remotion's internal HTTP server serves them seamlessly via `staticFile()`.
- `render_video()`: Invokes `remotion render` with `--concurrency=2` (optimized for 7840U 8-core CPU), generating H.264 High profile, yuv420p, 30 fps, AAC 48kHz audio. Automatically exports a 1080x1920 cover frame at the peak visual moment.
- `render_still_frame()`: Invokes `remotion still` for instantaneous golden-frame visual regression testing.
- `generate_contact_sheet()`: Combines 6 sampled frames per video across recent renders into a single high-resolution contact sheet PNG using ffmpeg's `tile` filter.

---

## 2. How It Was Verified

Acceptance checks were executed in `tests/integration/test_phase3_render.py`:
- **Safe Area Bounds**: Verified caption and card coordinates adhere strictly to Instagram safe area boundaries.
- **Contract Integrity**: Verified `props.json` schema matches Remotion root expectations.
- **Golden Frame Image Verification**: Rendered frames 30 (Hook), 180 (Conversation), 450 (Action Card), and 700 (End Card) from `ReelA-Split`, verifying complete image generation (> 10KB PNGs).
- **Multi-Layout & Multi-Palette Verification**: Rendered 6 preview videos covering:
  - Layouts: `ReelA-Split`, `ReelB-Phone`, `ReelC-Chat`
  - Palettes: `midnight_indigo`, `emerald_luxury`, `sunset_crimson`, `cyber_slate`, `royal_amethyst`, `warm_amber`
  - All 6 `.mp4` video files generated successfully with valid size and audio-video streams.
- **Contact Sheet Generation**: Successfully assembled multi-video frame contact sheet with ffmpeg tile filter.
- **Execution Result**:
  `tests/integration/test_phase3_render.py::test_phase3_remotion_renderer_and_golden_frames PASSED [100%]` in 122 seconds.

---

## 3. What Is Known to Be Weak / Limits

1. **CPU Rendering Throughput**:
   Rendering a 5-second preview takes ~15-20 seconds per video on the 7840U CPU. A full 30-second video takes approximately 1.5 to 2.5 minutes. While comfortably below the 10-minute per-video wall-clock budget, concurrency should remain capped at 2-3 threads to leave memory headroom for other OS tasks.
2. **Audio URL Resolution in Chromium**:
   Remotion's headless Chromium shell rejects raw `file:///` URLs for HTML5 `<Audio>` elements due to browser security restrictions. Master audio tracks must be staged in `render/public/audio/` and referenced via `staticFile()`.
3. **Remotion Licensing Awareness**:
   Remotion is free for individuals and small entities up to their stated team/revenue limits (see Remotion Company License). If the company scales past these thresholds, a commercial Remotion license will be required.
