"""Test planner diversity constraints over N=30 plans."""
from reelforge.pipeline.stages.planner import run_planner_batch


def test_planner_diversity_30_runs():
    plans = run_planner_batch(n=30, dry_run=True)
    assert len(plans) == 30

    verticals = [p["axes"]["vertical"] for p in plans]
    cities = [p["axes"]["city"] for p in plans]
    scenarios = [p["axes"]["scenario"] for p in plans]
    hooks = [p["axes"]["hook_style"] for p in plans]

    # Acceptance 1: >= 10 distinct verticals across 30 runs
    distinct_verticals = set(verticals)
    assert len(distinct_verticals) >= 10, f"Found only {len(distinct_verticals)} verticals: {distinct_verticals}"

    # Acceptance 2: No vertical repeated within 5
    for i in range(len(verticals)):
        window = verticals[i + 1 : i + 6]
        assert verticals[i] not in window, f"Vertical {verticals[i]} repeated within 5: {window}"

    # Acceptance 3: No two consecutive identical on hard-cooldown axes
    for i in range(len(plans) - 1):
        assert verticals[i] != verticals[i + 1], f"Consecutive vertical collision at {i}"
        assert cities[i] != cities[i + 1], f"Consecutive city collision at {i}"
        assert scenarios[i] != scenarios[i + 1], f"Consecutive scenario collision at {i}"
        assert hooks[i] != hooks[i + 1], f"Consecutive hook collision at {i}"
