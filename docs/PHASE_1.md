# Phase 1 Documentation: Diversity Engine & Business Generator

## 1. Summary of What Was Built

### Layer 1: Wide Taxonomy (`src/reelforge/diversity/taxonomy.py`)
- **22 Verticals:** From Hair Salon, Barbershop, Nail Studio, Dental Front Desk, Physiotherapy Clinic, Pet Grooming, Restaurant/Cafe, Bakery, Plumbing, Electrical, AC Repair, Auto Repair, Real Estate, Law Office, to Tutoring and Florist Boutique. Sensitive clinics and law scenarios are marked `is_sensitive_administrative_only = True`.
- **14 Locales:** Cities across India (Pune, Jaipur, Kochi, Lucknow, Bengaluru, Indore, Delhi NCR, Mumbai, Hyderabad, Chandigarh) and international hubs (Singapore, Dubai, London, Austin) carrying realistic currency symbols, time formats, fictional phone patterns, and regional professional registers.
- **Scenarios & Personas:** 13 distinct call scenarios (new bookings, reschedules, cancellations, after-hours urgencies, FAQ resolutions, escalations) paired with 4 business personas and 6 caller moods/age bands.
- **Visual & Audio Taxonomies:** 3 layouts (`ReelA-Split`, `ReelB-Phone`, `ReelC-Chat`), 12 curated palettes, 6 OFL font pairings, 3 caption styles (`word-highlight`, `karaoke`, `boxed`), 3 motion curves, and Kokoro voice pairs with gender differentiation.

### Layer 2: Cooldown Constraint Engine (`src/reelforge/diversity/cooldown.py`)
- Enforces hard cooldown rules against historical plans:
  - Vertical: 5 past videos (and **never consecutive**)
  - Locale City: 6 past videos
  - Scenario Type: 4 past videos
  - Hook Style: 8 past videos
  - Layout + Palette combination: 6 past videos; Palette alone: 3 past videos
  - Voice Pair: 4 past videos; Agent Voice frequency: maximum 2 of the last 5
- **Deterministic Relaxation Ladder:**
  `palette_alone -> voice_pair -> layout_palette -> hook_style -> city -> scenario -> vertical`. Invariant constraints (business name uniqueness and consecutive vertical repetition) are strictly non-relaxable.

### Layer 3 & 4: Novelty Sampler & Semantic Fingerprinting (`sampler.py`, `fingerprint.py`)
- Thompson sampling bandit with Beta priors over performance arms, guarded by a mandatory `>=30%` exploration floor.
- Word 3-gram extraction and Jaccard similarity calculation.
- Cosine similarity evaluation using `nomic-embed-text` embeddings.
- SQLite persistence in `fingerprints` table.

### Stage 1 Planner & Stage 2 Business Generator (`planner.py`, `profile.py`)
- CLI command `reelforge plan --n N --dry-run` for interactive inspection.
- Fictional business generator outputting structured Pydantic `BusinessProfile` objects with 6-12 realistic priced services, 5 FAQs, operating hours, and booking constraints.
- Real-brand denylist guard and 3-attempt validation and repair loop.

---

## 2. Verification & Acceptance Checks

### Acceptance Check 1: 30 Plan Diversity Dry Run
Execution:
```powershell
.\.venv\Scripts\python.exe -m reelforge.cli plan --n 30 --dry-run
```
- Yielded 30 diverse plans.
- Generated 18 distinct verticals (exceeding the `>= 10` requirement).
- No vertical repeated within 5.
- Zero consecutive duplicate axes.

### Acceptance Check 2: Automated Pytest Suite
Execution:
```powershell
.\.venv\Scripts\pytest.exe -v
```
Result: **10 PASSED in 1.43s**
- `test_consecutive_vertical_forbidden`: PASSED
- `test_vertical_cooldown_within_5`: PASSED
- `test_city_cooldown_within_6`: PASSED
- `test_scenario_cooldown_within_4`: PASSED
- `test_hook_style_cooldown_within_8`: PASSED
- `test_layout_palette_combo_cooldown`: PASSED
- `test_agent_voice_max_in_5`: PASSED
- `test_relaxation_sequence_order`: PASSED
- `test_planner_diversity_30_runs`: PASSED
- `test_generate_15_business_profiles_zero_collisions`: PASSED (15 generated profiles, 0 collisions, 100% schema compliance).

---

## 3. Known Weaknesses & Mitigations

1. **Brand Name Hallucinations:** Free-form LLM generation could occasionally coin a name closely resembling a local store.
   - *Mitigation:* Integrated `FAMOUS_BRAND_DENYLIST`, database history lookups, and a deterministic synthetic generator for 100% collision-free fallbacks.
2. **Bandit Cold Start:** With fewer than 15 published videos, bandit statistics can have high variance.
   - *Mitigation:* Enforced uninformative uniform priors (`Beta(1,1)`) when published video count is under 15, plus a permanent 30% exploration floor.
