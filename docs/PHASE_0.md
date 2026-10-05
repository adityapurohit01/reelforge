# Phase 0 Documentation: Scaffolding, Toolchain & Benchmarks

## 1. Summary of What Was Built

### Core Infrastructure & Packaging
- **Python Virtual Environment (`.venv`):** Configured via `pyproject.toml` and installed using `uv`. Houses all core dependencies:
  - CLI & Contracts: `typer`, `rich`, `pydantic>=2.7`, `pydantic-settings`
  - Persistence: `sqlmodel`, `sqlalchemy` (SQLite database)
  - Audio & DSP: `soundfile`, `pyloudnorm`, `pydub`, `scipy`, `numpy`
  - Speech & Alignment: `faster-whisper`, `kokoro-onnx`, `ctranslate2`
  - Cloud & Social: `boto3`, `httpx`, `python-telegram-bot`, `apscheduler`
  - Testing: `pytest`, `respx`
- **Remotion Video Renderer (`render/`):** React 18 + TypeScript Remotion setup.
  - Bundled with `@remotion/cli` (v4.0.533) and Chrome Headless Shell.
  - Compositions created and validated: `ReelA-Split`, `ReelB-Phone`, `ReelC-Chat`.
  - Design system tokens implemented: 12 curated color palettes, OFL font pairings (Inter, Outfit, Plus Jakarta Sans, DM Sans, Space Grotesk, Cinzel), and spring motion profiles.
  - Component library built: Animated `Waveform`, safe-area `Captions`, `ActionChips`, `NotificationCard`, `BookingCard`, `HookCard`, and `EndCard`.
- **Database Architecture (`src/reelforge/models.py`, `src/reelforge/db.py`):**
  - Fully typed SQLModel schemas for `businesses`, `plans`, `videos`, `fingerprints`, `approvals`, `publish_log`, `metrics`, `bandit_stats`, and `runs`.
  - Auto-initializing SQLite engine with foreign key constraints.
- **Diagnostics & CLI (`src/reelforge/cli.py`):**
  - Interactive Typer CLI with `doctor`, `plan`, `generate`, `resume`, `approve`, `publish`, `metrics`, and `report` subcommands.

---

## 2. Verification & Acceptance Checks

### Acceptance Check 1: `reelforge doctor`
Execution:
```powershell
.\.venv\Scripts\python.exe -m reelforge.cli doctor
```
Result: **PASSED (ALL GREEN)**
```
                            ReelForge System Health                            
┌────────────────────────┬──────────────┬─────────────────────────────────────┐
│ Component              │ Status       │ Details                             │
├────────────────────────┼──────────────┼─────────────────────────────────────┤
│ Python Environment     │ PASSED       │ Python 3.12.11 with core packages   │
│ Node.js                │ PASSED       │ v22.19.0 (C:\Program Files\nodejs)  │
│ FFmpeg                 │ PASSED       │ ffmpeg version 8.1.2-full_build     │
│ Ollama & Models        │ PASSED       │ Server online. Models: llama3.2,    │
│                        │              │ llama3.1, nomic-embed-text          │
│ SQLite DB              │ PASSED       │ reelforge.db initialized with schema│
│ Telegram Bot           │ UNCONFIGURED │ Required for Phase 4                │
│ Storage                │ PASSED       │ Local storage mode active           │
│ Instagram API          │ UNCONFIGURED │ Required for live Phase 5           │
└────────────────────────┴──────────────┴─────────────────────────────────────┘
[OK] Toolchain and environment ready!
```

### Acceptance Check 2: Remotion Composition Verification
Execution:
```powershell
.\render\node_modules\.bin\remotion.cmd compositions render/src/index.ts
```
Result: **PASSED (Bundled in 3462ms)**
- `ReelA-Split`: 1080x1920 @ 30fps (900 frames / 30.00 sec)
- `ReelB-Phone`: 1080x1920 @ 30fps (900 frames / 30.00 sec)
- `ReelC-Chat`: 1080x1920 @ 30fps (900 frames / 30.00 sec)

---

## 3. Local Model Benchmarks (AMD Ryzen 7840U CPU, 16 GB Shared RAM)

Executed via `scripts/benchmark_llm.py` across multiple generation trials on this machine:

| Model | Architecture | Speed (tok/s) | Avg Latency | RAM (Ollama Process) | Status / Selection |
|---|---|---|---|---|---|
| **llama3.2:3b** | 3.2B Q4_K_M | **13.04 tok/s** | **78.28s** | ~52 MB process (~2.1 GB VRAM/RAM) | **Primary Default for Generation** |
| **llama3.1:latest** | 8.0B Q4_K_M | 5.98 tok/s | >120s (Timeout) | ~548 MB process (~5.0 GB VRAM/RAM) | High-capacity Fallback Model |
| **nomic-embed-text** | 137M F16 | Real-time (<0.05s) | <0.05s | ~80 MB | **Deduplication Embedding Engine** |

### Benchmark Analysis & Architecture Decisions:
1. **CPU Speed vs Wall-Clock Budget:** The per-video budget is under 10 minutes. `llama3.1:latest` running on CPU generates at ~6 tokens/s and frequently hits the 120s request ceiling for complex JSON structures. In contrast, `llama3.2:3b` generates at **13.04 tokens/s**, generating complete structured outputs in under 80 seconds without memory pressure.
2. **Memory Discipline (`keep_alive: 0`):** By unloading the Ollama model immediately following generation, system RAM is immediately reclaimed before Kokoro TTS synthesis and Remotion headless Chrome rendering.

---

## 4. Known Weaknesses & Mitigations

1. **Windows Console Unicode/cp1252 Handling:** Standard Windows terminal defaults to cp1252 encoding. Uncaught Unicode emojis (e.g. 🔍, ✅) raise `UnicodeEncodeError`. 
   - *Mitigation:* Explicitly invoked `sys.stdout.reconfigure(encoding="utf-8")` and standardized on robust ASCII tags (`[OK]`, `[FAIL]`, `[*]`) in CLI outputs.
2. **Remotion Composition ID Syntax:** Remotion rejects underscores in composition IDs (`ReelA_Split` raises a validation error).
   - *Mitigation:* Standardized composition identifiers to hyphenated format (`ReelA-Split`, `ReelB-Phone`, `ReelC-Chat`).
3. **LLM Structured Output Stability:** Raw prompt generation occasionally omitted minor sub-schema fields.
   - *Mitigation:* Phase 1 integrates a strict 3-attempt validation and repair loop using Pydantic schemas.
