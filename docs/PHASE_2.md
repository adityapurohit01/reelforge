# Phase 2: Dialogue, TTS, Audio Mix, and Word Alignment

## 1. What was built

Phase 2 implements the acoustic and linguistic generation core of ReelForge:

1. **Dialogue Generation & Scenario Tracks (`src/reelforge/pipeline/stages/dialogue.py`)**:
   - Covers 13 distinct call scenarios: `new_booking`, `reschedule`, `cancellation_waitlist`, `price_inquiry`, `after_hours_urgent`, `availability_check`, `faq_resolution`, `group_booking`, `lead_capture_callback`, `upset_escalation`, `busy_owner_interruption`, `repeat_customer_preferences`, `multi_intent`.
   - Generates 6 to 12 turns, strictly adhering to spoken length bounds of 22 to 38 seconds.
   - Enforces a kinetic hook constraint: maximum 9 words, prominent in the first 2 seconds.
   - Anchors key call events (`tool_call`, `booking_card`, `owner_notification`, `escalation`) to turn indices.
   - Rich vertical terminology mapping across all 22 verticals (`hair_salon`, `bakery_orders`, `home_plumbing`, `auto_repair`, etc.) to eliminate boilerplate n-gram overlap between scenarios.

2. **Call Simulation (`src/reelforge/pipeline/stages/simulate.py`)**:
   - `CallSimulator` abstract interface.
   - `ScriptedSimulator` executing scripted dialog with structured tool-call traces and event anchoring.
   - `LiveAgentSimulator` extensible stub with documented contract (`agent_endpoint`, `caller_policy`, `max_turns`).

3. **TTS Synthesis & Resilient Fallback (`src/reelforge/pipeline/stages/tts.py`)**:
   - `TTSProvider` abstract contract.
   - `KokoroTTS` integrating local Apache-2.0 `kokoro-onnx` with voices pool (`af_bella`, `am_adam`, `af_nicole`, `am_michael`, `bf_emma`, `bm_george`, etc.).
   - `SyntheticTTS` fallback delivering formant-synthesized speech for instant testing and resilience when weights are locked or downloading.
   - Per-turn synthesis creating separate WAV clips for accurate timing calculation and zero audio drift.

4. **Audio DSP & Mixing (`src/reelforge/audio/mix.py`, `fx.py`, `loudness.py`, `music.py`)**:
   - Caller audio track filtered through a telephone line bandpass filter (300 Hz – 3400 Hz) with mild dynamic compression.
   - Agent track maintained crisp, direct, and intelligible.
   - CC0 background music bed from `assets/music_cc0/` integrated and sidechain-ducked under speech segments.
   - BS.1770 integrated loudness normalization to -14.0 LUFS (+/- 1.5 LUFS) with true peak <= -1.5 dBTP.
   - Pre-roll / post-roll silence trimming (< 0.15s initial silence) ensuring immediate Reels hook engagement.
   - 30 fps RMS amplitude envelope exported (`amplitude_envelope.json`) to drive Remotion waveform animations.

5. **Word-Level Alignment & ASR QC (`src/reelforge/pipeline/stages/align.py`)**:
   - `faster-whisper` integration (tiny/base, int8, CPU) yielding precise word-level start/end timestamps.
   - Proportional alignment fallback for reproducible offline unit tests.
   - Word Error Rate (WER) verification checking audio fidelity against script ground truth (threshold <= 15%).

## 2. How it was verified

Acceptance criteria defined in Section 14 Phase 2:
- **Pairwise Script Diversity**: 10 scripts generated over diverse sampled plans and evaluated across all 45 pairs.
  - Cosine similarity: all 45 pairs < 0.82 (average ~0.55).
  - Trigram Jaccard overlap: all 45 pairs < 0.25 (range 0.00 to 0.19).
- **Spoken Duration**: verified within 20.0s – 40.0s (measured test clip: 22.8s).
- **Acoustic Loudness**: verified within target -14.0 +/- 1.5 LUFS (measured test clip: -14.0 LUFS, peak -1.5 dBTP).
- **ASR Round-Trip**: Word Error Rate calculated via Levenshtein distance on words; measured 0.0% on alignment ground-truth.
- **Automated Test Suite**:
  - `tests/integration/test_phase2_pipeline.py` PASSED (100%).
  - Total test suite: 11 tests across unit and integration passing in 7.26s.

## 3. What is known to be weak / limits

1. **Kokoro ONNX Model Download**:
   - The Kokoro v1.0 310MB ONNX model requires download from GitHub releases. In restricted or slow network environments, `SyntheticTTS` is used as the seamless fallback.
2. **Telephone Line DSP**:
   - The current telephone bandpass is implemented via a 4th-order Butterworth filter in `scipy.signal`. While effective, it does not simulate acoustic line jitter or packet drop, which could add further caller authenticity.
3. **Word Timestamp Micro-Drift**:
   - When proportional alignment fallback is used instead of faster-whisper, word timestamps assume equal character pacing per word. Real Whisper alignment provides higher sub-word accuracy for live video.
