# ReelForge System Architecture & Design Decisions

This document details the architectural decisions, pipeline contracts, and design trade-offs behind **ReelForge**, an autonomous marketing video generation system for an AI voice-receptionist startup ("Vocalis AI").

---

## 1. High-Level System Architecture

ReelForge is structured as a typed, resumable state machine running entirely locally on an AMD Ryzen 7840U laptop with 16 GB shared RAM and no CUDA/NVIDIA GPU.

```
                           ┌───────────────────────────────────────────┐
                           │            SQLite Database State          │
                           │ businesses · plans · videos · fingerprints│
                           │ publish_log · metrics · bandit_stats      │
                           └───────────────▲───────────────────────────┘
                                           │
  Scheduler / CLI ──► [Stage 1: Planner] ──► [Stage 2: Business Generator]
                       (Taxonomy + Bandit)       (Fictional Profile + Repair)
                                                       │
                                                       ▼
                      [Stage 4: Call Sim] ◄── [Stage 3: Dialogue Writer]
                       (Scripted / Live)         (Turns, Events, Hook, CTA)
                               │
                               ▼
                      [Stage 5: TTS & Mix] ──► [Stage 6: Word Alignment]
                       (Kokoro ONNX, -14LUFS)    (Whisper / Levenshtein)
                                                       │
                                                       ▼
                      [Stage 8: QC Gates]  ◄── [Stage 7: Remotion Render]
                       (Safe areas, WER,         (Props.json -> MP4/Cover)
                        Claims, Freeze)                │
                               │                       ▼
                               ▼             [Stage 9: Instagram Captions]
                      [Stage 10: Telegram]     (Hooks, Hashtags, Alt Text)
                       (Founder Approval)
                               │ (approved)
                               ▼
                      [Stage 11: Upload] ────► [Stage 12: Instagram Publish]
                       (Cloudflare R2)           (Reels Container -> Poll)
                                                       │
                                                       ▼
                                             [Stage 13: Metrics & Bandit]
                                               (24h/72h/7d Engagement Feedback)
```

---

## 2. Key Design Decisions & Rejected Alternatives

### 2.1 Video Composition: Remotion vs. Playwright + HTML Canvas vs. FFmpeg Complex Filters

* **Chosen Architecture:** **Remotion v4** (React + TypeScript), parameterized by a unified `props.json` contract and rendered via Remotion CLI using Chrome Headless Shell.
* **Why:**
  * Remotion guarantees **frame-perfect determinism**: animations are pure functions of `frame / fps` rather than wall-clock `requestAnimationFrame`.
  * Allows leveraging full React/CSS ecosystems: Flexbox layouts, dynamic SVG waveforms, spring physics (`spring()`), and typography.
  * Audio waveforms are accurately rendered using frame-indexed RMS envelopes computed during the audio mix stage.
* **Rejected Alternative 1: Playwright + HTML Canvas Frame Capture**
  * *Trade-off:* While Playwright avoids Remotion's commercial license limitations at scale, recording smooth 30 fps 1080x1920 canvas video via Playwright screenshot loops suffers from frame jitter, CPU thread saturation, and audio desynchronization.
* **Rejected Alternative 2: Pure FFmpeg Filter Graphs (`drawtext`, `showwaves`)**
  * *Trade-off:* FFmpeg complex filters are brittle, extremely painful to maintain across 3 responsive layouts, lack modern typography layout features (line-wrapping, auto-clamping, spring animations), and make design iterations prohibitive.

---

### 2.2 Audio Synthesis: Per-Turn Synthesis vs. Single Full-Script Synthesis

* **Chosen Architecture:** **Per-turn audio synthesis** followed by deterministic DSP mixing (`pydub` / `scipy` / `pyloudnorm`).
* **Why:**
  * Exact timing control: each conversational turn has a distinct duration, allowing precise alignment of on-screen action chips, speaker indicators, and captions.
  * Individual channel DSP: the caller turn receives bandpass telephone filtering (300–3400 Hz) and mild compression, while the AI receptionist remains clean and crystal-clear.
  * Micro-variations: allows inserting natural conversational pauses (`pause_after_ms`), speed jitter (+/- 6%), and crossfaded interruptions (80–150ms).
* **Rejected Alternative: Single Whole-Script TTS Generation**
  * *Trade-off:* Generating the whole dialogue in one pass causes speaker bleed, timing drift between speakers, inability to apply phone audio effects to only the caller, and renders action-chip anchor timing unpredictable.

---

### 2.3 Cloud Storage: Cloudflare R2 vs. Local Tunnels (ngrok / Cloudflare Tunnel)

* **Chosen Architecture:** **Cloudflare R2** via S3-compatible API (`boto3`) with randomized UUID object keys.
* **Why:**
  * Meta's Instagram Graph API requires publicly accessible HTTPS URLs with correct `Content-Type: video/mp4` to download media containers.
  * R2 offers **zero egress fees**, 99.99% availability, and instantaneous download speeds for Meta's servers.
  * Intermediate upload objects are cleanly deleted after the container status reports `FINISHED`.
* **Rejected Alternative: Local Tunnels (ngrok / Localtunnel)**
  * *Trade-off:* Tunnel URLs change across restarts, frequently trigger Meta anti-abuse or security interstitial blocks, and expose the local machine's ports to inbound connections.

---

### 2.4 Diversity & Bandit: Thompson Sampling with Permanent Exploration Floor vs. Epsilon-Greedy

* **Chosen Architecture:** **Multi-Armed Bandit with Thompson Sampling** over Beta priors $\text{Beta}(\alpha, \beta)$ combined with a **hard 30% exploration floor** and cooldown rules.
* **Why:**
  * Thompson sampling naturally balances exploration and exploitation based on posterior uncertainty: rarely explored arms retain high variance, giving them opportunities to be tested.
  * The **30% exploration floor** structurally guarantees that even if a specific vertical (e.g. "Hair Salon") or hook performs exceptionally well, the system will never collapse into posting only that vertical.
  * Cooldown rules (no vertical within 5 videos, no duplicate business name, max 1 consecutive layout) always take precedence over bandit priors.
* **Rejected Alternative: Standard $\epsilon$-Greedy or Pure Random**
  * *Trade-off:* Pure random fails to learn from audience retention and conversion signals. Standard $\epsilon$-greedy does not account for posterior variance and tends to over-exploit early winners before adequate sample sizes are collected.

---

### 2.5 Memory Discipline (16 GB Shared RAM on CPU)

* **Design Rule:** The LLM, TTS, and Remotion video renderer are **never loaded into memory simultaneously**.
* **Implementation:**
  1. Ollama LLM requests explicitly pass `keep_alive: 0` to flush model weights from RAM immediately after profile and dialogue generation.
  2. TTS and audio mixing run sequentially, writing WAV files to disk and clearing numpy buffers.
  3. Remotion CLI executes in a subprocess with `--concurrency=2`, leaving plenty of memory for Windows and system tasks.
  4. End-to-end RAM consumption stays below 6 GB throughout the entire pipeline run.
