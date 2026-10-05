# PROJECT: ReelForge — autonomous marketing-video pipeline for an AI voice-receptionist company

You are a senior engineer building this system end to end, autonomously. Work in phases (section 14). Before writing code, produce an implementation plan and a task list (as artifacts if you support them). After the plan, proceed without waiting for approval. Stop and ask only when you need a credential or an external account action that you cannot do yourself. After each phase, run the phase's acceptance checks, fix failures, and write a short `docs/PHASE_n.md` stating what was built, how it was verified, and what is known to be weak. Never mark a phase done on the strength of "it should work"; run it.

---

## 1. Context and goal

The company sells an **AI voice receptionist for small businesses**. It answers phone calls on behalf of the owner, handles real tasks (bookings, rescheduling, FAQs, lead capture, escalation to a human) and notifies the owner on WhatsApp or Telegram with a summary.

Build **ReelForge**, a local pipeline that:

1. Plans a *new, deliberately different* short vertical marketing video each run.
2. Invents a fictional small business and a realistic customer-call scenario for it.
3. Writes the call dialogue, voices both sides with an open-source TTS, and renders a polished 1080x1920 video of the call (live captions, animated waveform, agent "actions" appearing, and the owner notification card).
4. Runs automated quality gates.
5. Sends the result to the founder on Telegram for approval.
6. On approval, uploads it and publishes it as an Instagram Reel through the official Instagram Graph API.
7. Collects performance metrics and feeds them back into what gets planned next.

**The single most important product requirement: no two videos may feel the same.** Different business, vertical, city, owner, services, caller, scenario, outcome, voices, hook style, layout, palette, typography and pacing. Section 6 defines the diversity engine and is a hard requirement with automated enforcement and tests.

## 2. Hard constraints

- **Target machine:** laptop with an AMD Ryzen AI 7 (7840U), 16 GB shared RAM, **no NVIDIA GPU / no CUDA**. Everything must run on CPU. Assume Windows 11 (keep it fully cross-platform: `pathlib`, no bash-only scripts, no hard-coded separators).
- **No paid services required for the core path.** Core models are open source and local. Allowed free-tier infrastructure: Telegram Bot API, Cloudflare R2 (or any S3-compatible bucket), Meta's Instagram Graph API.
- **No generative video models.** The video is *composed* (templates + animation + real audio), not diffusion-generated. Leave a clean optional plugin interface `BrollProvider` (stub only) so generated B-roll can be added later on a rented GPU.
- **Memory discipline (16 GB):** never hold the LLM, TTS and renderer in memory simultaneously. Unload the LLM (`keep_alive: 0` in Ollama) before the TTS and render stages. Stages run sequentially.
- **Per-video wall-clock budget on the target machine:** under about 10 minutes end to end for a 30-second video. Log per-stage timings and flag regressions.
- **Reproducibility:** every video has a `seed`; the same plan + seed reproduces the same output (LLM temperature aside; store the LLM outputs so a replay uses stored text).
- **Secrets** only in `.env` (never committed), loaded via pydantic-settings. Provide `.env.example`.

## 3. Tech stack (use these unless you find a concrete blocker, and then document the swap)

| Layer | Choice | Notes |
|---|---|---|
| Orchestrator / CLI | Python 3.11+, Typer, Pydantic v2 | Typed contracts between stages |
| State | SQLite via SQLModel or SQLAlchemy | Single file DB, resumable runs |
| LLM | Ollama, 7-8B instruct model at Q4 (model name in config) | Benchmark 2-3 candidates on this machine in Phase 0 and pick by quality/speed. JSON-schema constrained output (Ollama `format`) with validate-and-repair loop. Provider interface so an API model can be swapped in. |
| Embeddings (dedup) | Small local embedding model (e.g. `nomic-embed-text` via Ollama, or `all-MiniLM-L6-v2` via sentence-transformers) | CPU-friendly |
| TTS | **Kokoro-82M** (Apache-2.0) via `kokoro-onnx` or the official package | CPU real-time. Provider interface; **Piper** as fallback. Optional `ChatterboxProvider` stub for hero clips. |
| Audio DSP | `pyloudnorm`, `scipy.signal`, `pydub` / ffmpeg | Loudness, phone-line effect, ducking |
| Alignment | `faster-whisper` (tiny/base, int8, CPU) for word timestamps per turn clip; fallback: proportional timing from known per-turn durations | Also used for the ASR round-trip QC |
| Video composition | **Remotion** (React + TypeScript), driven by a single `props.json`, rendered with the Remotion CLI | Python calls it via subprocess. Note in `docs/` that Remotion's license is free only up to its stated team-size limits, so re-check before hiring. Fallback design: HTML templates + Playwright frame capture + ffmpeg. |
| Encoding | ffmpeg | H.264 High, yuv420p, 30 fps, AAC 48 kHz, `+faststart` |
| Approval | Telegram bot (`python-telegram-bot` or `aiogram`) | Whitelisted chat ID only |
| Storage | `StorageBackend` interface: `R2Storage` (S3 API via boto3), `LocalTunnelStorage` (dev) | Instagram needs a public video URL |
| Publishing | Instagram Graph API (Content Publishing) via `httpx` | Details in section 10 |
| Scheduling | APScheduler in-process, plus docs for Windows Task Scheduler | Timezone-aware |
| Tests | pytest, `respx` (HTTP mocking) | |
| Packaging | `uv` or `pip` + `pyproject.toml`; Node deps for Remotion in `/render` | One `reelforge doctor` command verifies the whole toolchain |

## 4. Architecture

```
                         ┌───────────────────────────────────────────┐
                         │                SQLite state               │
                         │ businesses · plans · videos · fingerprints│
                         │ publish_log · metrics · bandit_stats      │
                         └───────────────▲───────────────────────────┘
                                         │
 Scheduler/CLI ─► [1 Planner] ─► [2 Business Generator] ─► [3 Dialogue Writer]
                    (novelty +        (fictional profile,      (turns, events,
                     bandit)           JSON schema)             hook, CTA)
                                                                   │
        ┌──────────────────────────────────────────────────────────┘
        ▼
 [4 Call Simulator] ─► [5 TTS + Audio Mix] ─► [6 Alignment] ─► [7 Render (Remotion)]
  (ScriptedSim now,      (2 voices, phone       (word times,       (props.json →
   LiveAgentSim later)    FX, music, LUFS)       amplitude env)     mp4 + cover)
                                                                        │
        ┌───────────────────────────────────────────────────────────────┘
        ▼
 [8 QC Gates] ─► [9 Caption/Hashtag Writer] ─► [10 Telegram Approval]
   (hard fail →       (varied, no fake            (Approve / Reject /
    auto-regen)        claims)                     Regenerate / Edit)
                                                        │ approved
                                                        ▼
                         [11 Upload (R2)] ─► [12 Instagram Publish] ─► [13 Metrics + Bandit update]
                                                (container → poll → publish)   (24h / 72h / 7d)
```

Every stage is a pure-ish function `run(ctx) -> StageResult` with typed input/output, writes its artifacts into `runs/<run_id>/<stage>/`, and records state transitions. The pipeline is a **resumable state machine**:

`PLANNED → PROFILED → SCRIPTED → VOICED → ALIGNED → RENDERED → QC_PASSED → AWAITING_APPROVAL → APPROVED → UPLOADED → PUBLISHED → METRICS_COLLECTED`

plus `FAILED_<STAGE>` with retry counters and `REJECTED`. `reelforge resume <run_id>` continues from the last good state. Stages are idempotent: re-running a finished stage with the same inputs is a no-op unless `--force`.

## 5. Repository layout

```
reelforge/
  pyproject.toml  .env.example  config.yaml  README.md
  src/reelforge/
    cli.py                      # Typer: plan, generate, resume, approve, publish, metrics, doctor, report
    config.py                   # pydantic-settings, config.yaml loader
    db.py  models.py            # SQLModel tables
    pipeline/
      state_machine.py          # transitions, retries, resume
      stages/ planner.py profile.py dialogue.py simulate.py tts.py align.py render.py qc.py captions.py approve.py upload.py publish.py metrics.py
    diversity/
      taxonomy.py               # axes + values (section 6)
      sampler.py                # constraint-aware novelty sampler + bandit
      fingerprint.py            # n-gram + embedding similarity
      cooldown.py               # per-axis cooldown rules
    llm/ base.py ollama.py prompts/*.md schemas/*.json
    tts/ base.py kokoro.py piper.py voices.yaml
    audio/ mix.py fx.py loudness.py music.py
    social/ telegram_bot.py instagram.py storage.py
    qc/ checks.py claims_lint.py
    analytics/ insights.py bandit.py report.py
  render/                       # Remotion project (TypeScript)
    src/compositions/ ReelA_Split.tsx ReelB_Phone.tsx ReelC_Chat.tsx
    src/components/ Waveform.tsx Captions.tsx ActionChips.tsx BookingCard.tsx NotificationCard.tsx HookCard.tsx EndCard.tsx
    src/themes/ palettes.ts fonts.ts motion.ts
    public/fonts/ public/music/ public/icons/
  assets/ music_cc0/ fonts_ofl/ voices_samples/
  tests/ unit/ integration/ golden/
  runs/                         # per-run artifacts (gitignored)
  docs/ PHASE_0.md ... ARCHITECTURE.md RUNBOOK.md
```

## 6. The Diversity Engine (hard requirement)

The system must make repetition structurally impossible, not merely unlikely. Implement **four layers**.

### 6.1 Layer 1: a wide taxonomy of axes

`taxonomy.py` defines each axis as a list of weighted values with metadata. The values below show the *breadth expected*, not an exhaustive or hard-coded list. The generator must invent new businesses within them; never reuse a business.

- **Vertical (at least 14):** hair salon, barbershop, nail/beauty studio, dental clinic front desk (administrative only), physiotherapy clinic, veterinary clinic, restaurant/cafe, bakery pre-orders, home services (plumber, electrician, AC repair), cleaning service, auto repair/garage, real-estate agency, law/accounting front desk (administrative only), yoga/fitness studio, driving school, tutoring/coaching center, photography studio, pet grooming, spa/wellness, hotel/guesthouse, moving company, florist.
- **Locale (at least 12):** cities across India (Pune, Jaipur, Kochi, Lucknow, Bengaluru, Indore...), plus a few international (Taipei, Singapore, Dubai, Nairobi, Manchester, Austin). Each locale carries currency, typical phone format (always fictional/obviously fake), name pools, time format, weekday-weekend convention, and a language register. The agent speaks English by default; allow a per-locale `speech_style` (e.g. Indian English phrasing) without caricature.
- **Business persona:** solo owner / family-run / small team of 3-8 / multi-branch; formality (warm-casual to polished); price tier.
- **Caller persona:** age band, mood (rushed, curious, anxious, cheerful, impatient, confused), accent hint for voice selection, relationship (new/returning/referred).
- **Scenario type:** new booking · reschedule · cancellation with waitlist fill · price/quote inquiry · after-hours urgent request · availability check · FAQ (parking, hours, policies) · group/large-party booking · lead capture (viewing request, quote request) · upset customer escalated to human · "owner is busy with a customer" interruption · repeat customer with preferences · multi-intent call (asks 2 things).
- **Outcome:** booked · rescheduled · lead captured and callback set · escalated to human with context · FAQ resolved · waitlist filled.
- **Hook style (at least 8, each a template family with slots):** "POV: owner with hands full" · "3 AM emergency" · question hook · "watch this call" · contrast (missed call vs handled call) · "what the owner sees on their phone" · rapid cold open (first spoken line is the caller's) · myth-bust. **No invented statistics, and no fake "X% of calls are missed" claims.**
- **Visual axes:** layout (A split / B phone / C chat), palette (>= 12 curated, plus hue jitter within bounds that preserve contrast), font pairing (>= 6 OFL pairs), background motif (procedural gradients/patterns keyed to vertical), icon set (Lucide/Tabler, MIT), caption style (>= 3: word-highlight, karaoke bar, boxed), motion profile (easing and speed), cover-frame style.
- **Audio axes:** agent voice and caller voice from the Kokoro voice pool (a pair must differ in gender-or-timbre and be clearly distinguishable), speech-rate jitter (+/- 6%), music bed (CC0 pool) and level, phone-line effect on/off per video.

### 6.2 Layer 2: cooldown constraints (hard rules; the sampler may never violate them)

Stored in `config.yaml`, enforced in `cooldown.py`, queried from the DB of past videos:

- Same **business name**: never. Same business *profile fingerprint*: never.
- Same **vertical**: not within the last 5 videos (and never 2 consecutive).
- Same **locale city**: not within the last 6.
- Same **scenario type**: not within the last 4.
- Same **hook style**: not within the last 8.
- Same **layout + palette combination**: not within the last 6; same palette alone: not within the last 3.
- Same **voice pair**: not within the last 4; same agent voice: not more than 2 of the last 5.
- Same **first spoken line** or same CTA phrasing: not within the last 15.

If the constraints leave no feasible combination, relax in a defined priority order (log which constraint was relaxed and why), never silently.

### 6.3 Layer 3: semantic de-duplication gate

After the dialogue is generated and before any rendering:

- Compute an embedding of the full script and of the hook line separately. **Reject and regenerate** (max 3 attempts, with an escalating "be more different from these recent examples" instruction that lists the last N hooks and opening lines) if cosine similarity to any of the last 50 scripts is >= 0.82, or hook similarity >= 0.85.
- Compute word 3-gram Jaccard overlap against the last 50 scripts; reject at >= 0.25.
- Reject if the business name, owner name, or any service name collides with history.
- Store every accepted fingerprint (embeddings + n-gram sets + axis tuple) in `fingerprints`.

### 6.4 Layer 4: novelty-aware sampling with performance feedback

`sampler.py` scores every feasible combination:

`score = novelty_score(least-recently-used distance across axes) + exploration_bonus + performance_prior`

- `performance_prior` comes from a Thompson-sampling bandit over (vertical, hook style, scenario type, layout) arms, updated from Instagram Insights (saves, shares, average watch time weighted over raw views). With fewer than N=15 published videos, use uniform priors (pure exploration).
- Keep a permanent **exploration floor**: at least 30% of picks ignore the performance prior so the system never collapses into repeating "what worked".
- Cooldowns always override the bandit.

### 6.5 Visibility and proof

- `reelforge report diversity --last 30` prints: axis coverage histogram, longest repeat streak per axis, pairwise similarity heatmap summary, constraint relaxations used.
- A contact sheet (`ffmpeg tile` of 6 frames per video, last 12 videos on one PNG) is generated so a human can eyeball variety.

## 7. Data model (SQLite)

- `businesses(id, name, vertical, city, locale, owner_name, profile_json, fingerprint_id, created_at)`
- `plans(id, run_id, axis_tuple_json, seed, relaxations_json, created_at)`
- `videos(id, run_id, business_id, state, script_json, audio_path, video_path, cover_path, duration_s, loudness_lufs, qc_report_json, caption, hashtags_json, created_at)`
- `fingerprints(id, script_embedding BLOB, hook_embedding BLOB, trigram_set BLOB, axis_tuple_json)`
- `approvals(id, video_id, decision, decided_by, decided_at, note)`
- `publish_log(id, video_id, container_id, media_id, permalink, status, error, attempts, published_at)`
- `metrics(id, video_id, window, reach, views, likes, comments, saves, shares, avg_watch_time_s, fetched_at)`
- `bandit_stats(arm_key, alpha, beta, n, updated_at)`
- `runs(run_id, state, started_at, finished_at, stage_timings_json, error)`

Migrations via Alembic or a simple versioned SQL folder.

## 8. Stage specifications

### Stage 1: Planner
Input: DB history + config. Output: `Plan` (axis tuple + seed). Implements section 6.2 and 6.4. CLI: `reelforge plan --n 20 --dry-run` prints plans without generating anything (used in the diversity test).

### Stage 2: Business Generator
LLM call with a JSON schema. Produce a **fictional** small business: name (not a known real brand; avoid generic collisions by checking against history and a small local denylist of famous brands), tagline, owner first name, city/neighborhood, hours, 6-12 services with plausible local-currency prices, 5-8 FAQ answers (parking, cancellation policy, payment methods, etc.), staff list, booking rules (slot lengths, buffer, closed days), tone of voice. Validate the schema; run the repair loop on failure (max 3). **Realism rules:** prices must be plausible for the vertical and locale; hours must be internally consistent; no real phone numbers (use obviously fictional patterns, or show none on screen).

### Stage 3: Dialogue Writer
Input: Plan + BusinessProfile. Output `DialogueScript`:

```
hook_text            # on-screen text, <= 9 words, first 2 s
turns[]: {speaker: "agent"|"caller", text, emotion, pause_after_ms, on_screen_event?}
events[]: {t_anchor_turn, type: "tool_call"|"booking_card"|"owner_notification"|"escalation", payload}
owner_notification   # the exact message the owner receives (summary, name, time, service, contact, next step)
cta_text, caption_seed, hashtags_seed
```

Rules: 6-12 turns, **spoken length 22-38 seconds**; natural speech (contractions, brief fillers, one interruption or clarification maybe); the agent is helpful, concise and never pretends to be human if sincerely asked; the call must **resolve** in the stated outcome; the agent's tool calls (check calendar → slot found → booked → confirmation sent) must be consistent with the business's booking rules and hours; the first spoken line must obey the hook-style template; end with a one-line CTA for the company (product name and URL from config). No invented statistics, no guarantees, no testimonials, no medical, legal or financial advice (clinic/law scenarios are strictly administrative).

### Stage 4: Call Simulator
Interface `CallSimulator.run(script, profile) -> SimulatedCall`.
- `ScriptedSimulator` (Phase 2): uses the LLM-written turns directly.
- `LiveAgentSimulator` (stub with documented contract, implemented later): drives the company's *real* voice agent with a scripted caller persona and records its actual responses and tool calls, so videos double as regression tests of the product. Define the interface now: `agent_endpoint`, `caller_policy`, `max_turns`, returns transcript + tool-call trace + audio if available.

### Stage 5: TTS and audio mix
- Synthesize each turn separately (per-turn WAV, so timings are exact), agent and caller with different voices from `voices.yaml`.
- Per-turn micro-variation: speed jitter, small pre-roll/post-roll pauses honoring `pause_after_ms`, overlap on interruptions (crossfade 80-150 ms).
- Caller track optionally gets a "phone line" effect (band-pass about 300-3400 Hz, mild compression); the agent stays clean.
- Add a **CC0 music bed** from `assets/music_cc0/` (random pick respecting cooldown), sidechain-ducked under speech, final integrated loudness about -14 LUFS, true peak <= -1.5 dBTP. Silence at start <= 0.15 s (Reels hook fast).
- Output: `mix.wav`, per-turn clips, `amplitude_envelope.json` (30 fps RMS for the waveform animation).

### Stage 6: Alignment
Run faster-whisper (tiny/base, int8) on each turn clip for word-level timestamps; fall back to proportional timing. Output `words.json` with `{word, start, end, speaker}` and event times (anchors from section 8.3).

### Stage 7: Render (Remotion)
Python writes `props.json`: theme tokens, layout, fonts, palette, motif, caption style, words, events, amplitude envelope, business display data, audio path, durations. Renders `1080x1920 @ 30 fps` mp4 plus a cover PNG.

Scenes and requirements:
1. **Hook card (0-2.5 s):** large kinetic text; animated background from the vertical's motif; the audio starts immediately.
2. **Call view:** a stylized phone-call UI (business name, call timer), a **waveform driven by the real amplitude envelope** (different color per speaker), and **word-by-word captions** in the chosen style, safe-area aware for Instagram's UI overlays (keep key content out of the bottom ~20% and the top ~10%).
3. **Agent actions rail:** chips that animate in at event times ("Checked calendar", "Slot found: Thu 4:30 PM", "Booked", "Confirmation sent"), with icons.
4. **Owner notification card:** a messenger-style notification (WhatsApp-like or Telegram-like *stylization*, not a pixel copy of their logos or trademarks) that slides in with the exact `owner_notification` text.
5. **End card (last 2-3 s):** product name, one-line value statement, CTA, URL/handle from config.
6. A small, always-visible footer label: **"Simulated call - fictional business"**.

Three layouts (A split, B full-phone, C chat-style) must be *structurally* different, not recolors. All animation timing derives from `words.json` and `events`, never from fixed frame counts. Fonts bundled locally (OFL). Provide `reelforge render --run <id> --preview` that renders a 5 s low-res preview, and a golden-image test that renders still frames at 3-4 timestamps.

Encode with ffmpeg: H.264 High, yuv420p, 30 fps, AAC 48 kHz 160 kbps, `-movflags +faststart`, file < 100 MB. Cover frame: choose the hook frame or a high-contrast frame, export 1080x1920 PNG/JPEG.

### Stage 8: QC gates (automatic; any hard failure triggers regeneration of the failing stage, max 2 retries, then notify the founder)
Hard checks:
- Duration 20-40 s; resolution/fps/codec correct; audio present.
- Loudness within -14 +/- 1.5 LUFS; true peak within limit; no silence longer than 1.2 s; no clipping.
- **ASR round trip:** transcribe the final audio with faster-whisper and compare to the script; word error rate must be <= 15% (catches TTS glitches).
- Captions fit inside safe areas on every sampled frame (the renderer emits a layout report; or detect overflow via DOM measurement in Remotion).
- No black/blank frames, no frozen frames longer than 1.5 s (ffmpeg `blackdetect`, `freezedetect`).
- **Claims lint** (`claims_lint.py`): fail on invented statistics, guarantees ("never miss", "100%", "guaranteed"), medical/legal/financial advice, competitor names, real-brand names, phone numbers.
- Diversity gate re-check (section 6.3) against the final script.
Soft checks produce warnings in the approval message (e.g. pacing, long words on screen).
Output `qc_report.json`.

### Stage 9: Caption and hashtags
LLM-written Instagram caption: first line is a hook that differs from the on-video hook; 2-3 short lines; one clear CTA; 3-5 relevant hashtags (vertical + local + product category), varied across posts (no identical hashtag block twice in a row); a short disclosure line that the call is simulated. Also write alt text. Run the claims lint on it.

### Stage 10: Telegram approval
The bot sends the video, cover, business summary, scenario/axes used, QC report summary and the proposed caption with inline buttons: **Approve**, **Reject (with reason)**, **Regenerate (same business, new seed)**, **New video (different plan)**, **Edit caption**. Only whitelisted chat IDs can act. Default policy: **never publish without approval** (`auto_publish` is off; if enabled in config, require QC soft-warning count == 0 and a configurable delay). Persist decisions in `approvals`. Reject reasons feed back into planning (e.g. a rejected layout gets a temporary penalty).

### Stage 11: Upload
`StorageBackend.upload(video, cover) -> public_https_url`. R2 implementation with a randomized object key, a bucket policy or signed URL valid for 24 h, and cleanup of objects after publish succeeds. The video URL must be directly fetchable by Meta (no redirects to HTML pages, correct `Content-Type: video/mp4`).

### Stage 12: Instagram publish
See section 10.

### Stage 13: Metrics and learning
Jobs at 24 h, 72 h and 7 d after publish pull Insights for the media (reach, views, likes, comments, saves, shares, average watch time where available; check which metrics the current API version supports for Reels). Store them, update `bandit_stats` per section 6.4, and include them in `reelforge report performance`.

## 9. Configuration (`config.yaml` + `.env`)

`.env`: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_CHAT_IDS`, `IG_USER_ID`, `IG_ACCESS_TOKEN`, `META_APP_ID`, `META_APP_SECRET`, `GRAPH_API_VERSION`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_PUBLIC_BASE_URL`, `OLLAMA_HOST`.

`config.yaml`: product name, CTA URL/handle, brand colors for the end card, languages/locales enabled, videos per day, publish time windows with timezone, cooldown numbers (section 6.2), similarity thresholds, LLM model names, TTS voice pools, duration bounds, QC thresholds, `auto_publish: false`, `dry_run: true` by default.

## 10. Instagram publishing specification

**Do not rely on remembered endpoint details. Before coding this module, read the current official Meta documentation for Instagram Content Publishing (Reels) and confirm: the API host and version, whether to use Instagram Login or Facebook Login, the exact permission scopes, the media container fields for Reels, and the current daily publishing limit endpoint.** Then implement:

1. **Preconditions:** Instagram Business or Creator account (linked to a Facebook Page if the chosen login flow requires it), a Meta app, the account added as an app tester/role so it works in development mode without app review. Document these in `docs/INSTAGRAM_SETUP.md` as a step-by-step checklist for the founder, including how to generate a long-lived token.
2. **Flow:** (a) check the account's remaining publishing quota; (b) create a media container for a Reel with `video_url`, `caption`, optional `cover_url`, share-to-feed flag; (c) poll the container status with exponential backoff (e.g. 5 s → 30 s, total timeout about 10 min) until it reports finished; handle `ERROR`/`EXPIRED` with a clear message; (d) publish the container; (e) fetch the permalink and store `media_id`.
3. **Idempotency:** persist the `container_id` before publishing; on retry, reuse it; never double-publish (check `publish_log` first).
4. **Token lifecycle:** a scheduled job refreshes the long-lived token before expiry and alerts the founder on Telegram if refresh fails. Surface API error codes (rate limit, invalid token, media-processing failure) as clear Telegram alerts.
5. **Dry run:** `--dry-run` executes everything except the final publish call and shows what would be sent. Provide a mock server (`respx`) for integration tests.
6. **AI disclosure:** check whether the API exposes an AI-generated-content label field; if it does, set it; if not, the caption disclosure line plus the on-video "Simulated call" label are mandatory.

## 11. Compliance and brand-safety rules (enforced in code, not just prompts)

- Every video states on-screen that it is a simulated call with a fictional business. Never present it as a real customer or real testimonial.
- No real business names, real people, real phone numbers, or cloned voices of real people. Use only the bundled TTS voices.
- No invented performance claims about the product; claims may only come from an approved `claims.yaml` file that the founder edits (empty by default).
- Music only from CC0/public-domain assets with a `LICENSES.md` provenance file; fonts only OFL.
- Clinic/legal scenarios are administrative (scheduling, intake logistics) and never give advice.
- Do not scrape any website or platform. (A future "personalized prospect demo" feature, section 13, uses only data the founder supplies.)

## 12. Observability, errors and operations

- Structured JSON logs with `run_id`, stage, duration, retries. A `runs/<run_id>/manifest.json` records inputs, seeds, model names and versions, and artifact hashes.
- Telegram alerts for: stage failure after retries, QC failure, publish failure, token near expiry, disk space < 5 GB.
- `reelforge doctor` checks: Python deps, Node + Remotion, headless Chrome for Remotion, ffmpeg, Ollama reachability + model present, TTS model files, fonts, DB migrations, Telegram token validity, R2 write/read test, Instagram token validity and quota (no publish).
- Disk hygiene: keep full artifacts for the last 30 runs; keep only the final mp4 + manifest for older ones.

## 13. Extension points (stubs and interfaces only; do not build now)

- `LiveAgentSimulator` (section 8.4).
- `BrollProvider` for optional generated B-roll on rented GPUs.
- **Prospect demo mode:** `reelforge demo --business-json prospect.json` renders a personalized 30 s demo for one specific prospect using details the founder provides (name, services, hours), exporting an mp4 for WhatsApp or email rather than Instagram. Same pipeline, different input and no publish step. Design the `BusinessProfile` loader so this requires no refactor.
- Multi-language scripts and voices.

## 14. Build phases and acceptance criteria

**Phase 0: scaffolding and benchmarks.** Repo, config, DB, CLI skeleton, `doctor`. Benchmark 2-3 candidate local LLMs and Kokoro on this machine; record tokens/s, RAM, and a JSON-validity rate over 20 business-profile generations; choose defaults and document in `docs/PHASE_0.md`.
*Accept:* `reelforge doctor` is green; benchmark table committed.

**Phase 1: diversity engine + business generator.** Taxonomy, cooldowns, sampler, fingerprints, Stage 2.
*Accept:* `reelforge plan --n 30 --dry-run` yields plans with >= 10 distinct verticals, no vertical repeated within 5, no two consecutive identical on any hard-cooldown axis; unit tests for every cooldown and the relaxation order; generate 15 business profiles with 0 name collisions and 100% schema validity (after repair).

**Phase 2: dialogue + TTS + audio mix + alignment.**
*Accept:* generate 10 scripts; pairwise cosine similarity < 0.82 and 3-gram Jaccard < 0.25 for all pairs; all within 22-38 s spoken; mixed audio meets loudness spec; ASR round-trip WER <= 15% on all.

**Phase 3: Remotion renderer, three layouts, themes.**
*Accept:* render 6 videos covering all three layouts and >= 5 palettes; golden-frame tests pass; captions never overflow safe areas; a contact sheet shows visibly different videos.

**Phase 4: QC gates + Telegram approval.**
*Accept:* QC catches deliberately broken fixtures (silent audio, overlong clip, a claim like "100% guaranteed"); the bot's button flows work against a test chat; non-whitelisted chats are ignored.

**Phase 5: storage + Instagram publishing.**
*Accept:* integration tests against the mock Graph API cover success, processing timeout, `ERROR` status, token expiry, duplicate-publish protection; `--dry-run` works against the real account; a real test publish succeeds once the founder supplies credentials (log the permalink).

**Phase 6: metrics + bandit + reports.**
*Accept:* simulated metrics shift arm probabilities in the expected direction in tests; the exploration floor holds (verify by statistical test over 1,000 simulated picks); cooldowns are never violated even under strong priors.

**Phase 7: scheduler, docs, hardening.**
*Accept:* `reelforge run --n 3` generates three different videos from a clean DB and stops at approval; an interrupted run resumes correctly; `RUNBOOK.md`, `ARCHITECTURE.md` and `INSTAGRAM_SETUP.md` are complete; an end-to-end dry run produces a final report including the diversity report for the last videos.

## 15. Final deliverable checklist

- Working repo with all phases' acceptance checks passing, plus a one-command setup (`make setup` or `scripts/setup.ps1`).
- `docs/ARCHITECTURE.md` explaining each design decision **with the rejected alternatives and trade-offs** (for example Remotion vs Playwright, per-turn TTS vs whole-script, R2 vs tunnel, bandit vs random).
- A `docs/KNOWN_LIMITS.md` stating plainly what is weak or unverified (for example how natural the TTS sounds, Meta API behavior you could not test without credentials).
- A short founder checklist of the accounts and tokens needed (Telegram bot, Meta app + Instagram Business account, R2 bucket), in the order to set them up.

Begin with the implementation plan and task list, then start Phase 0.