# Phase 4 Documentation: QC Gates & Telegram Approval

## 1. What Was Built

Phase 4 implements automated quality assurance and human-in-the-loop founder approval before any generated media can reach public publishing.

### A. Automated Quality Control Gates (`src/reelforge/qc/checks.py`, `src/reelforge/pipeline/stages/qc.py`)
The QC system executes multi-layer hard and soft validation on the rendered video, audio master, script, and captions:
1. **Container & Video Standard**:
   - Resolution must be strictly 1080x1920 vertical.
   - Codec must be H.264 High Profile (`h264`), 30 fps.
   - Duration must fall strictly within configured bounds (20s to 40s).
2. **Audio Compliance**:
   - Integrated loudness measured with ITU-R BS.1770-4 meter, enforced within `-14.0 +/- 1.5 LUFS`.
   - Maximum true-peak clamped at `< -1.5 dBTP`.
   - Detected silence > 1.2s flagged as failure.
3. **Visual Glitch Detection**:
   - Invokes `ffmpeg` filter `freezedetect=n=0.003:d=1.5,blackdetect=d=0.8:pic_th=0.98` to catch frozen screens > 1.5s or black screen drops.
4. **ASR Round-Trip Verification**:
   - Calculates Word Error Rate (WER) using Levenshtein distance between original script words and speech hypothesis (`words.json`).
   - Hard failure triggered if WER > 15% (catches audio dropouts, mispronunciations, or TTS timing skips).
5. **Brand Safety & Claims Linter (`src/reelforge/qc/claims_lint.py`)**:
   - Enforces brand safety across dialogue scripts and Instagram captions.
   - Prohibits absolute guarantees ("100% guaranteed", "never miss", "zero errors", "we promise").
   - Prohibits invented statistics ("X% of calls", "X% increase", "X out of Y").
   - Prohibits clinical medical/legal/financial advice (prescriptions, dosages, diagnosis, lawsuit guarantees).
   - Prohibits mentions of competitors (Bland AI, Retell AI, Vapi, Synthflow).
   - Prohibits plausible non-fictional phone numbers (must follow obvious 555-fictional formats).
6. **Soft Warnings & Pacing**:
   - Emits advisory warnings for excessively rapid (> 210 WPM) or sluggish (< 120 WPM) speech delivery.
   - Generates structured `qc_report.json` in the run directory.

### B. Telegram Founder Approval Bot (`src/reelforge/social/telegram_bot.py`, `src/reelforge/pipeline/stages/approve.py`)
1. **Strict Whitelisting**:
   - Verifies incoming user and chat IDs against `TELEGRAM_ALLOWED_CHAT_IDS` loaded from environment/configuration. Unauthorized interactions are rejected with warning logs.
2. **Rich Briefing Message**:
   - Dispatches formatted Telegram Markdown summary containing:
     - Video ID, fictional business name, vertical, city, and owner.
     - Scenario, Remotion layout, palette, and voice pairing.
     - QC pass/fail status and exact audio/duration/WER metrics.
     - Proposed Instagram caption and hashtags.
3. **Interactive Inline Keyboard**:
   - `✅ Approve & Publish` (`approve:<video_id>`)
   - `❌ Reject` (`reject:<video_id>:<reason>`)
   - `🔄 Regenerate (Same Biz)` (`regen:<video_id>`)
   - `🆕 New Video (New Plan)` (`new_plan:<video_id>`)
   - `✏️ Edit Caption` (`edit_caption:<video_id>`)
4. **State Persistence**:
   - Callback responses are recorded in the `approvals` table in SQLite (`Approval` model) tracking `decision`, `decided_by`, `decided_at` (timezone-aware UTC), and optional rejection notes. Rejection notes directly inform subsequent novelty weighting.

---

## 2. How It Was Verified

Acceptance checks were verified in `tests/integration/test_phase4_qc_telegram.py`:
- **Claims Linter Verification**: Verified that guarantees ("100% guaranteed"), invented stats ("84% of calls"), medical prescriptions ("amoxicillin"), and competitor mentions ("Bland AI") trigger violations, while clean administrative dialogue passes without issue.
- **WER Levenshtein Algorithm**: Verified 0% error on exact match, ~12% on single substitution, and >70% on divergent transcripts.
- **Broken Fixtures Detection**: QC Gate confirmed to catch silent audio (< -70 LUFS), broken claims, and speech mismatch.
- **Valid Fixture Execution**: Verified clean passing run on calibrated -14 LUFS audio, standard script, and aligned words.
- **Telegram Whitelist & Callback Persistence**:
  - Non-whitelisted chats (ID `99999999`) blocked.
  - Whitelisted chats receive full inline button matrix.
  - Button actions (`approve` and `reject`) successfully write to SQLite `approvals` table.
- **HTTP Mock Dispatch**: Verified `/sendMessage` HTTP API call with `respx`.
- **Execution Result**:
  `tests/integration/test_phase4_qc_telegram.py` passed 6/6 tests in 2.24s.

---

## 3. What Is Known to Be Weak / Limits

1. **Telegram Bot Token Requirement**:
   Without a live Telegram Bot token in `.env`, the bot operates in mock mode. The mock mode exercises full formatting, button generation, and database state transitions, but live delivery requires the founder to provide `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ALLOWED_CHAT_IDS`.
2. **Regex-Based Claims Linting**:
   The claims linter relies on compiled regex patterns. While very fast and deterministic for common marketing traps, subtle or sarcastic unauthorized claims could bypass regex checks without a secondary LLM verification step.
