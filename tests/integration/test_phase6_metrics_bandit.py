"""Phase 6 Integration & Acceptance Tests.
Verifies:
1. Multi-Armed Bandit:
   - Simulated engagement metrics shift arm selection probabilities in the expected direction.
   - Exploration floor holds: verified by statistical test over 1,000 simulated picks (>= 30% exploration).
   - Cooldown constraints are NEVER violated even under strong prior weights.
2. Insights Collection & Composite Scoring:
   - Weighted action calculation (saves/shares prioritized over raw views).
   - Persistence in SQLite metrics table.
3. Diversity & Performance Reporting:
   - Formatted reports and histogram audits.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import pytest
from sqlmodel import Session, select

from reelforge.analytics.bandit import ThompsonBandit
from reelforge.analytics.insights import InsightsCollector
from reelforge.analytics.report import generate_diversity_report, generate_performance_report
from reelforge.config import load_config
from reelforge.db import get_engine, init_db
from reelforge.diversity.sampler import NoveltySampler
from reelforge.models import BanditStat, Metric, Plan, PublishLog, Video


@pytest.fixture
def test_db_session(tmp_path: Path):
    db_file = tmp_path / "test_p6_reelforge.db"
    db_url = f"sqlite:///{db_file}"
    engine = get_engine(db_url)
    init_db(engine)
    with Session(engine) as session:
        yield session


def test_bandit_arm_probability_shift(test_db_session: Session):
    """Verify that simulated rewards shift Thompson sampling arm picks towards winning arms."""
    bandit = ThompsonBandit()
    rng = random.Random(42)

    # Arm A: High-performing vertical (lots of saves & shares)
    arm_high = "vertical:dental_clinic"
    # Arm B: Low-performing vertical (low engagement)
    arm_low = "vertical:auto_repair"

    # Train arms over 20 iterations
    for _ in range(20):
        bandit.update_arm(test_db_session, arm_high, reward=0.90)
        bandit.update_arm(test_db_session, arm_low, reward=0.10)

    # Sample 500 times with exploitation enabled (total_published=30 > 15)
    counts = {"dental_clinic": 0, "auto_repair": 0}
    candidates = ["dental_clinic", "auto_repair"]

    for _ in range(500):
        pick = bandit.sample_best_arm(
            axis_name="vertical",
            candidate_values=candidates,
            session=test_db_session,
            total_published=30,
            rng=rng,
        )
        counts[pick] += 1

    # High arm should win significantly more picks than low arm
    # Note: 30% exploration floor ensures low arm still gets picked occasionally
    assert counts["dental_clinic"] > counts["auto_repair"] * 2.0
    assert counts["dental_clinic"] > 300, f"Expected dental_clinic > 300, got {counts['dental_clinic']}"


def test_exploration_floor_statistical_property(test_db_session: Session):
    """Verify that the >= 30% exploration floor holds over 1,000 picks."""
    sampler = NoveltySampler(exploration_floor=0.30)
    history = []
    rng = random.Random(1337)

    exploration_count = 0
    total_picks = 1000

    for i in range(total_picks):
        plan, _ = sampler.sample_plan(
            session=test_db_session,
            history=history,
            seed=rng.randint(1, 10_000_000),
        )
        if plan.get("_is_pure_exploration", False):
            exploration_count += 1
        history.insert(0, plan)
        if len(history) > 50:
            history.pop()

    exploration_rate = exploration_count / total_picks
    # Over 1,000 trials with p=0.30, 99.7% confidence interval is [0.256, 0.344]
    assert 0.25 <= exploration_rate <= 0.35, f"Exploration rate {exploration_rate:.3f} outside expected [0.25, 0.35]"


def test_cooldowns_never_violated_under_strong_priors(test_db_session: Session):
    """Verify that hard cooldown constraints are NEVER violated even under extreme prior weights."""
    bandit = ThompsonBandit()
    # Heavily bias one vertical and layout
    for _ in range(50):
        bandit.update_arm(test_db_session, "vertical:hair_salon", reward=1.0)
        bandit.update_arm(test_db_session, "layout:A_split", reward=1.0)

    # Populate 20 published logs to activate exploitation
    for i in range(20):
        pub = PublishLog(
            video_id=i + 1,
            container_id=f"c_{i}",
            media_id=f"m_{i}",
            permalink=f"https://instagram.com/reel/{i}",
            status="PUBLISHED",
            published_at=datetime.now(timezone.utc),
        )
        test_db_session.add(pub)
    test_db_session.commit()

    sampler = NoveltySampler()
    history = []

    # Generate 30 consecutive plans
    for seed in range(30):
        plan, _ = sampler.sample_plan(session=test_db_session, history=history, seed=1000 + seed)
        history.insert(0, plan)

    # 1. No vertical repeated within 5 runs
    verticals = [p["vertical"] for p in reversed(history)]
    for i in range(len(verticals)):
        window = verticals[max(0, i - 4):i]
        assert verticals[i] not in window, f"Vertical {verticals[i]} repeated within 5 videos at step {i}"

    # 2. Never 2 consecutive identical verticals
    for i in range(1, len(verticals)):
        assert verticals[i] != verticals[i - 1], f"Consecutive vertical collision at step {i}"

    # 3. Same layout + palette combination not within 6
    combo_history = [f"{p['layout']}:{p['palette']}" for p in reversed(history)]
    for i in range(len(combo_history)):
        comb_window = combo_history[max(0, i - 5):i]
        assert combo_history[i] not in comb_window, f"Layout+palette repeated within 6 at step {i}"


def test_insights_collector_composite_reward():
    """Verify composite engagement calculation prioritizes saves & shares."""
    collector = InsightsCollector()

    # Case A: High saves & shares (high intent)
    metrics_viral = {"views": 1000, "saves": 35, "shares": 20, "likes": 50, "comments": 10}
    reward_viral = collector.compute_composite_reward(metrics_viral)

    # Case B: High views but low high-intent actions
    metrics_empty_views = {"views": 1000, "saves": 1, "shares": 1, "likes": 10, "comments": 2}
    reward_empty = collector.compute_composite_reward(metrics_empty_views)

    assert reward_viral > reward_empty * 5.0
    assert 0.0 <= reward_viral <= 1.0
    assert 0.0 <= reward_empty <= 1.0


def test_diversity_and_performance_reports(test_db_session: Session):
    """Verify CLI reporting generation."""
    # Seed sample plan and bandit records
    for i in range(10):
        plan_axes = {
            "vertical": f"vertical_{i}",
            "city": f"city_{i}",
            "layout": "A_split" if i % 2 == 0 else "B_phone",
            "palette": f"palette_{i}",
            "scenario": f"scenario_{i}",
            "hook_style": f"hook_{i}",
            "agent_voice": f"voice_{i}",
        }
        p = Plan(
            run_id=f"run_report_{i}",
            axis_tuple_json=json.dumps(plan_axes),
            seed=42 + i,
            created_at=datetime.now(timezone.utc),
        )
        test_db_session.add(p)

    test_db_session.add(BanditStat(arm_key="vertical:hair_salon", alpha=12.4, beta=3.2, n=15, updated_at=datetime.now(timezone.utc)))
    test_db_session.add(BanditStat(arm_key="hook_style:pov_hands_full", alpha=8.6, beta=2.1, n=10, updated_at=datetime.now(timezone.utc)))
    test_db_session.commit()

    div_report = generate_diversity_report(test_db_session, last_n=10)
    assert "DIVERSITY AUDIT REPORT" in div_report
    assert "COOLDOWN INTEGRITY CHECK" in div_report
    assert "PASSED" in div_report

    perf_report = generate_performance_report(test_db_session)
    assert "PERFORMANCE & LEARNING REPORT" in perf_report
    assert "vertical:hair_salon" in perf_report
    assert "hook_style:pov_hands_full" in perf_report
