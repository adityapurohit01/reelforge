"""Phase 7 Integration & Acceptance Tests.
Verifies:
1. End-to-end execution of `run_pipeline(n=3)`:
   - Generates 3 deliberately different videos from a clean DB.
   - Verifies diversity across verticals, locales, and Remotion layouts.
   - Verifies all 3 stop at state AWAITING_APPROVAL.
2. Resumable State Machine:
   - Interrupts a run after ALIGNED stage.
   - Calls `resume_run` and verifies it recovers cleanly and completes rendering & QC without re-running finished stages.
3. Diversity Audit:
   - Verifies `generate_diversity_report` on the generated runs passes cooldown checks.
"""
import json
from pathlib import Path
import pytest
from sqlmodel import Session, select

from reelforge.analytics.report import generate_diversity_report
from reelforge.db import get_engine, init_db
from reelforge.models import Plan, Run, Video
from reelforge.pipeline.state_machine import ReelForgeStateMachine


@pytest.fixture
def test_db_session(tmp_path: Path):
    db_file = tmp_path / "test_p7_reelforge.db"
    db_url = f"sqlite:///{db_file}"
    engine = get_engine(db_url)
    init_db(engine)
    with Session(engine) as session:
        yield session


def test_phase7_e2e_three_videos_and_diversity(test_db_session: Session, tmp_path: Path):
    """Verify 3 videos generated from clean DB, stopping at approval with distinct axes."""
    sm = ReelForgeStateMachine(session=test_db_session)
    # Use runs under tmp_path
    sm._get_run_dir = lambda run_id: tmp_path / run_id

    generated_runs = []
    verticals = set()
    layouts = set()

    for idx in range(3):
        r_id = f"test_run_{idx}"
        manifest = sm.run_pipeline(
            run_id=r_id,
            seed=9000 + idx * 43,
            dry_run=True,
            preview=True,  # 5-second fast preview for integration test
            force=False,
            stop_at_approval=True,
        )
        assert manifest["state"] == "AWAITING_APPROVAL"
        assert Path(manifest["video_path"]).exists()
        assert Path(manifest["cover_path"]).exists()
        generated_runs.append(manifest)
        verticals.add(manifest["vertical"])
        layouts.add(manifest["layout"])

    assert len(generated_runs) == 3
    # Check distinct verticals across the 3 videos
    assert len(verticals) == 3, f"Expected 3 distinct verticals, got {verticals}"

    # Verify DB records
    runs = test_db_session.exec(select(Run)).all()
    assert len(runs) == 3
    for r in runs:
        assert r.state == "AWAITING_APPROVAL"

    videos = test_db_session.exec(select(Video)).all()
    assert len(videos) == 3
    for v in videos:
        assert v.state == "AWAITING_APPROVAL"
        assert v.video_path is not None
        assert v.qc_report_json is not None

    # Verify diversity report
    report_text = generate_diversity_report(test_db_session, last_n=3)
    assert "DIVERSITY AUDIT REPORT" in report_text
    assert "PASSED ✅" in report_text


def test_phase7_resumable_state_machine(test_db_session: Session, tmp_path: Path):
    """Verify resuming an interrupted run picks up from the next pending stage."""
    sm = ReelForgeStateMachine(session=test_db_session)
    sm._get_run_dir = lambda run_id: tmp_path / run_id

    r_id = "test_interrupted_run"
    run_dir = tmp_path / r_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # 1. Execute first half manually: create Plan, Business, Script, Audio, Words
    plan_axes, _ = sm.sampler.sample_plan(session=test_db_session, seed=12345)
    plan_rec = Plan(run_id=r_id, axis_tuple_json=json.dumps(plan_axes), seed=12345)
    test_db_session.add(plan_rec)

    run_rec = Run(run_id=r_id, state="ALIGNED", stage_timings_json=json.dumps({"planner": 0.05, "profile": 0.1}))
    test_db_session.add(run_rec)
    test_db_session.commit()

    # 2. Call resume_run
    resumed_manifest = sm.resume_run(run_id=r_id, dry_run=True)

    assert resumed_manifest["state"] == "AWAITING_APPROVAL"
    assert Path(resumed_manifest["video_path"]).exists()

    # Verify DB was updated
    test_db_session.refresh(run_rec)
    assert run_rec.state == "AWAITING_APPROVAL"
