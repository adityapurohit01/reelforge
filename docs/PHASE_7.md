# Phase 7 Documentation: Scheduler, State Machine Hardening & E2E Validation

## 1. What Was Built

Phase 7 hardens the pipeline into a resumable, fault-tolerant autonomous system, completes end-to-end multi-video orchestration, provides one-command setup, and documents operational procedures.

### A. End-to-End Pipeline State Machine (`src/reelforge/pipeline/state_machine.py`)
1. **Resumable State Transitions**:
   - `PLANNED -> PROFILED -> SCRIPTED -> VOICED -> ALIGNED -> RENDERED -> QC_PASSED -> AWAITING_APPROVAL -> APPROVED -> UPLOADED -> PUBLISHED -> METRICS_COLLECTED`.
   - Plus `FAILED_<STAGE>` and `REJECTED` states.
2. **Idempotence & State Recovery**:
   - `resume_run(run_id)` reads state from SQLite and run directory. Previously verified artifacts (`dialogue.json`, `mix.wav`, `words.json`, `[run_id].mp4`) are preserved, allowing an interrupted run to resume at the exact pending stage without duplicate LLM tokens or TTS cycles.
3. **Execution Manifests**:
   - Each run writes a complete `runs/<run_id>/manifest.json` capturing the seed, business profile, Remotion composition ID, palette, per-stage wall-clock timings, and video asset paths.
4. **Approval Boundary**:
   - By default (`stop_at_approval=True`), `reelforge run` completes rendering, audio, and QC validation, dispatches the briefing to Telegram, and safely parks in state `AWAITING_APPROVAL`.

### B. Unified CLI Interface (`src/reelforge/cli.py`)
- `reelforge doctor`: Toolchain diagnostics (Python, Node, FFmpeg, Ollama, SQLite, Telegram, R2, Instagram).
- `reelforge plan --n <N> [--dry-run]`: Generates N diversity plans.
- `reelforge run --n <N> [--preview] [--dry-run]`: Generates N complete videos stopping at approval.
- `reelforge resume <run_id>`: Resumes interrupted runs.
- `reelforge approve <run_id> [-d APPROVE|REJECT]`: Founder manual decision recording.
- `reelforge publish <run_id>`: Cloud upload and Instagram Reels container publishing.
- `reelforge metrics [--video-id <id>]`: Engagement polling and bandit update.
- `reelforge report diversity` / `reelforge report performance`: Structured ASCII reporting.
- `reelforge demo --business-json prospect.json`: Personalized prospect demo renderer.

### C. System Documentation & Automated Deployment
- `docs/ARCHITECTURE.md`: Complete system architecture diagram, component contracts, and design decisions with rejected alternatives and trade-offs.
- `docs/RUNBOOK.md`: Daily operational guidelines, Windows Task Scheduler automation, troubleshooting, and disk hygiene.
- `docs/KNOWN_LIMITS.md`: Explicit statements of CPU rendering latency, offline ONNX TTS characteristics, Meta API token lifecycle, and SQLite bounds.
- `docs/FOUNDER_CHECKLIST.md`: Sequential account setup guide (Telegram -> Meta App -> Cloudflare R2).
- `docs/INSTAGRAM_SETUP.md`: Meta Developer App configuration and 60-day token generation guide.
- `scripts/setup.ps1`: One-command automated Windows PowerShell setup.

---

## 2. How It Was Verified

Acceptance checks were verified in `tests/integration/test_phase7_e2e_pipeline.py`:
- **Three-Video Generation from Clean DB**:
  - Ran `run_pipeline` for 3 consecutive videos.
  - Confirmed 3 structurally distinct videos generated with 3 unique verticals and layouts.
  - All 3 videos passed container, loudness, audio peak, freeze frame, and safe area QC checks.
  - All 3 safely parked in state `AWAITING_APPROVAL` with manifests and cover frames generated.
- **Resumable State Machine Verification**:
  - Initialized an interrupted run stopped after `ALIGNED`.
  - Executed `resume_run` and confirmed it picked up from `RENDER -> QC -> AWAITING_APPROVAL` without re-running finished stages.
- **Execution Result**:
  `tests/integration/test_phase7_e2e_pipeline.py` passed 2/2 tests in 121.95s.

---

## 3. What Is Known to Be Weak / Limits

1. **Sequential Batch Timing on CPU**:
   Rendering 3 preview videos (5s each) plus audio and alignment takes ~2 minutes. Generating 3 full 30-second videos end-to-end on the AMD Ryzen 7840U CPU takes approximately 6-8 minutes total, well within the 10-minute per-video wall-clock budget.
2. **Windows Task Scheduler Service Dependencies**:
   Windows Task Scheduler jobs require the laptop to be awake or configured with "Wake the computer to run this task" enabled under Power Options.
