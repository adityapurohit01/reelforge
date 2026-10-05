# ReelForge Known Limits & Operational Constraints

This document provides a frank, transparent assessment of the system's operational boundaries, known weak spots, and external dependencies.

---

## 1. Hardware & Compute Constraints

* **AMD Ryzen 7840U (CPU-Only, 16 GB Shared RAM):**
  * The system does not require an NVIDIA GPU or CUDA drivers.
  * **Rendering Throughput:** A 5-second preview video takes ~15–20 seconds to compose in Remotion; a complete 30-second 1080x1920 vertical video takes ~1.5 to 2.5 minutes. This is well below the target 10-minute wall-clock budget.
  * **Remotion Concurrency:** Capped at `--concurrency=2`. Attempting `--concurrency=8` causes memory pressure and Chromium process thrashing on 16 GB systems.
  * **Sequential Stage Discipline:** The LLM, TTS, and Remotion video renderer are never run concurrently in memory.

---

## 2. Audio & Speech Synthesis Nuances

* **Kokoro-82M ONNX Model:**
  * Model size is 310 MB; executes at real-time factor ~0.2x on CPU.
  * While significantly more natural than legacy concatenative engines (e.g. Festival or Espeak), prosody can sound slightly robotic on rapid medical or legal proper nouns.
  * Turn-by-turn speed jitter (+/- 6%) and telephone bandpass filtering (300–3400 Hz) mask synthetic artifacts effectively for the phone caller track.
  * A stubbed `ChatterboxProvider` is documented for future hero-clip enhancements if cloud GPU resources become available.

---

## 3. Meta Instagram Graph API Operational Limits

* **60-Day Token Expiration:**
  * Meta long-lived user access tokens expire after 60 days.
  * While `refresh_long_lived_token()` extends valid tokens, if the pipeline is left inactive for > 60 days, a founder must manually generate a fresh token via Meta Graph API Explorer.
* **Rolling 24-Hour Quota:**
  * Meta enforces a hard limit of **50 API-published posts per 24 hours** per Instagram Professional account. ReelForge verifies quota before container initialization.
* **Unverified Production Edge Cases:**
  * Real Instagram publishing cannot be fully exercised without valid founder credentials (`IG_USER_ID`, `IG_ACCESS_TOKEN`). All Phase 5 acceptance tests were validated against strict HTTP mocks with `respx` mirroring official Meta v21.0 payloads.
* **AI Content Labeling:**
  * Current Meta API exposes caption and on-video overlays for synthetic content. ReelForge enforces compliance via the permanent on-screen label `"Simulated call • Fictional business"` and mandatory caption disclosures.

---

## 4. State & Concurrency

* **SQLite Local Database:**
  * State is maintained in a single-file SQLite database (`reelforge.db`) using SQLModel.
  * Ideal for single-laptop local autonomous execution (`check_same_thread: False`).
  * If the pipeline is later refactored into a distributed fleet across multiple cloud workers, the database layer should be migrated to PostgreSQL.
