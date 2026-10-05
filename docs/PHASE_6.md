# Phase 6 Documentation: Metrics, Multi-Armed Bandit Learning & Reports

## 1. What Was Built

Phase 6 implements the feedback and learning layer of **ReelForge**, completing Stage 13 and Layer 4 of the Diversity Engine. It enables the pipeline to continuously learn from audience engagement (saves, shares, watch time) while structurally guaranteeing exploration and variety.

### A. Multi-Armed Bandit with Thompson Sampling (`src/reelforge/analytics/bandit.py`)
1. **Beta Priors**:
   - Maintains independent Beta distributions $\text{Beta}(\alpha, \beta)$ for each arm across critical video axes: `vertical`, `hook_style`, `scenario`, and `layout`.
   - Priors are persisted in the SQLite `bandit_stats` table.
2. **Cold Start Exploration**:
   - For accounts with fewer than 15 published videos ($N < 15$), bandit arms use uniform priors ($\text{Beta}(1, 1)$) to gather baseline data before attempting exploitation.
3. **Permanent Exploration Floor**:
   - Enforces a hard **30% exploration floor**: regardless of how well an arm performs, at least 30% of picks ignore the performance priors and sample uniformly from valid candidates. This structurally prevents the pipeline from collapsing into repetitive local optima.
4. **Cooldown Primacy**:
   - Cooldown constraints strictly override the bandit. An arm with high expected return is eliminated from the candidate set if it violates cooldown rules (e.g. vertical within 5 videos, consecutive layout, or recent hook style).

### B. Engagement Insights & Composite Scoring (`src/reelforge/analytics/insights.py`)
1. **High-Intent Weighting**:
   - Raw vanity views are discounted. High-intent engagement is prioritized using the formula:
     $$\text{Composite Score} = \frac{3 \cdot \text{saves} + 2 \cdot \text{shares} + \text{likes} + 2 \cdot \text{comments}}{\max(\text{views}, 50)}$$
   - Scores are normalized into a $[0.0, 1.0]$ reward scalar.
2. **Lifecycle Polling**:
   - Designed for scheduled polling intervals at 24h, 72h, and 7d post-publishing.
   - Saves metrics to SQLite `metrics` table with timestamps and window labels.
   - Feeds normalized reward back into the bandit to update $\alpha \leftarrow \alpha + r$ and $\beta \leftarrow \beta + (1 - r)$.

### C. Reporting & Visualization (`src/reelforge/analytics/report.py`)
1. **`reelforge report diversity --last 30`**:
   - Prints unique axis counts across recent runs.
   - Calculates longest repeat streaks (guaranteeing $\le 1$ for hard cooldown axes).
   - Generates ASCII distribution histograms for verticals and layouts.
   - Evaluates cooldown integrity checks.
2. **`reelforge report performance`**:
   - Displays aggregated views, saves, shares, and average retention.
   - Ranks top-performing bandit arms with their Beta priors and expected conversion win rates.

---

## 2. How It Was Verified

Acceptance checks were verified in `tests/integration/test_phase6_metrics_bandit.py`:
- **Arm Probability Shift**:
  - Arm `vertical:dental_clinic` trained with high reward ($r=0.90$) and `vertical:auto_repair` with low reward ($r=0.10$).
  - Sampled 500 times with Thompson sampling.
  - Dental clinic won > 300 picks, confirming significant probability shift toward the high-performing arm.
- **Exploration Floor Statistical Property**:
  - Sampled 1,000 consecutive plans with `exploration_floor=0.30`.
  - Confirmed empirical exploration rate falls within the 99.7% confidence interval $[0.25, 0.35]$.
- **Cooldown Inviolability Under Strong Priors**:
  - Heavily trained `hair_salon` with 50 consecutive max rewards ($r=1.0$).
  - Generated 30 consecutive plans.
  - Verified:
    1. Zero vertical repeats within 5 videos.
    2. Zero consecutive identical verticals.
    3. Zero layout+palette repeats within 6 videos.
- **Composite Scoring Verification**:
  - Confirmed high saves/shares score $> 5\times$ higher than high-view/low-intent scenarios.
- **Report Generation**:
  - Verified ASCII diversity and performance report rendering.
- **Execution Result**:
  `tests/integration/test_phase6_metrics_bandit.py` passed 5/5 tests in 34.49s.

---

## 3. What Is Known to Be Weak / Limits

1. **Simulated vs Production Insights**:
   In dev environments without an active Instagram post receiving public traffic, metrics are mocked or tested with deterministic engagement fixtures. Real Insights collection requires the media to be public and viewed by Instagram users.
2. **Thompson Sampling Independent Arm Assumption**:
   Currently, the bandit optimizes marginal arm distributions independently (e.g. $P(\text{vertical})$, $P(\text{layout})$) rather than full joint cross-product arms $(V \times L \times S \times H)$. This avoids the curse of dimensionality across millions of permutations while allowing rapid convergence on small datasets.
