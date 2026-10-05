# ReelForge 🎬

Autonomous marketing-video pipeline for AI voice-receptionist companies.

ReelForge creates high-diversity, polished 1080x1920 vertical marketing videos of customer calls to fictional small businesses, complete with real TTS audio, live captions, animated audio waveforms, agent action chips, and owner notification cards.

## Features
- **4-Layer Diversity Engine:** Taxonomy, hard cooldown constraints, semantic embedding deduplication, and Thompson sampling bandit.
- **CPU-Optimized Audio Pipeline:** Kokoro-82M TTS + faster-whisper alignment with LUFS loudness normalization and phone-line acoustics.
- **Remotion Video Rendering:** 3 distinct layouts (Split, Phone, Chat), dynamic kinetic typography, and safe-area compliant captions.
- **Automated QC Gates:** Acoustic checks, WER transcription validation, claims safety linter, and freeze-frame detection.
- **Founder Approval Bot:** Telegram bot integration with inline approval/rejection feedback.
- **Social Publishing:** Direct Instagram Graph API Reels publishing with status polling and token management.

## Setup
```bash
# Set up Python virtual environment and dependencies
uv venv .venv
uv pip install --python .\.venv\Scripts\python.exe -e .

# Verify toolchain health
reelforge doctor
```
