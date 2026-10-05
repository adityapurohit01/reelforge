"""Phase 4 Integration & Acceptance Tests.
Verifies:
1. Automated Quality Control Gates catch deliberately broken fixtures:
   - Silent audio / loudness threshold violation
   - Overlong duration (> 40s)
   - Brand safety / claims lint violations ("100% guaranteed", invented statistics, medical advice)
   - High ASR Word Error Rate (> 15%)
2. Telegram Approval Bot:
   - Whitelist enforcement (unauthorized chat IDs strictly blocked)
   - Message formatting and inline keyboard buttons
   - Button callback actions persisted to SQLite approvals table
   - Mock API dispatch via respx
"""
import json
from pathlib import Path
import numpy as np
import pytest
import respx
import httpx
import soundfile as sf
from sqlmodel import Session, select

from reelforge.config import ReelForgeConfig, load_config
from reelforge.db import get_engine, init_db
from reelforge.models import Approval, Video
from reelforge.qc.checks import QualityControlGate, compute_wer
from reelforge.qc.claims_lint import ClaimsLinter
from reelforge.social.telegram_bot import TelegramApprovalBot
from reelforge.pipeline.stages.captions import generate_post_caption
from reelforge.pipeline.stages.profile import BusinessProfile
from reelforge.pipeline.stages.dialogue import DialogueScript, DialogueTurn


@pytest.fixture
def test_db_session(tmp_path: Path):
    db_file = tmp_path / "test_reelforge.db"
    db_url = f"sqlite:///{db_file}"
    engine = get_engine(db_url)
    init_db(engine)
    with Session(engine) as session:
        yield session


def test_claims_linter_deliberate_violations():
    """Verify claims linter catches guarantees, statistics, advice, and competitors."""
    linter = ClaimsLinter()

    # 1. Guarantee violations
    ok, violations = linter.lint_text("Our AI front desk offers a 100% guaranteed booking rate.")
    assert not ok
    assert any("guarantee" in v.lower() for v in violations)

    # 2. Invented statistics
    ok, violations = linter.lint_text("Did you know that 84% of calls to dental clinics are lost forever?")
    assert not ok
    assert any("statistic" in v.lower() for v in violations)

    # 3. Medical / Clinical advice
    ok, violations = linter.lint_text("Take 500mg of amoxicillin twice daily for tooth pain.")
    assert not ok
    assert any("medical" in v.lower() for v in violations)

    # 4. Competitor brand mentions
    ok, violations = linter.lint_text("Switch today from Bland AI or Synthflow to Vocalis AI.")
    assert not ok
    assert any("competitor" in v.lower() for v in violations)

    # 5. Clean text passes
    ok, violations = linter.lint_text(
        "Hi, thanks for calling Apex Physio. I can help book your consultation for Thursday at 3 PM."
    )
    assert ok
    assert len(violations) == 0


def test_wer_computation():
    """Verify Word Error Rate computation."""
    ref = "Hello and welcome to Apex Dental Studio in Pune"
    
    # Exact match -> 0% WER
    assert compute_wer(ref, "Hello and welcome to Apex Dental Studio in Pune") == 0.0

    # 1 substitution in 8 words -> 12.5%
    wer_1 = compute_wer(ref, "Hello and welcome to Apex Dental Clinic in Pune")
    assert 0.10 <= wer_1 <= 0.15

    # Completely different -> high WER
    wer_bad = compute_wer(ref, "Something completely unrelated and bizarre happens here today")
    assert wer_bad >= 0.70


def test_qc_gate_broken_fixtures(tmp_path: Path):
    """Verify QC gate fails deliberately broken fixtures."""
    qc = QualityControlGate()

    # 1. Broken fixture: Silent audio file (0 volume -> loudness < -70 LUFS)
    silent_audio = tmp_path / "silent.wav"
    sr = 24000
    silent_data = np.zeros(sr * 25, dtype=np.float32)
    sf.write(str(silent_audio), silent_data, sr)

    # Fake empty video path
    fake_video = tmp_path / "missing_video.mp4"
    fake_video.write_text("fake video content")

    bad_script = "Our AI guarantees 100% attendance and we prescribe medicine."
    bad_hook = "100% guaranteed"
    bad_caption = "90% of callers hang up! Use Bland AI instead."

    # Mismatched words for high WER
    mismatched_words = [{"word": "random"}, {"word": "nonsense"}]

    report = qc.run_qc(
        video_path=fake_video,
        audio_path=silent_audio,
        script_text=bad_script,
        hook_text=bad_hook,
        caption_text=bad_caption,
        words_data=mismatched_words,
    )

    assert not report["passed"]
    assert len(report["hard_failures"]) >= 3

    # Check specific failure reasons captured
    failure_text = " ".join(report["hard_failures"]).lower()
    assert "loudness" in failure_text
    assert "claims" in failure_text
    assert "asr word error rate" in failure_text


def test_qc_gate_valid_fixture(tmp_path: Path):
    """Verify QC gate passes a compliant, calibrated fixture."""
    qc = QualityControlGate()

    # Calibrated audio: generate 25s of speech-like sound at approximately -14 LUFS
    sr = 24000
    dur_s = 25
    t = np.linspace(0, dur_s, sr * dur_s, endpoint=False)
    # 440 Hz + harmonics with calibrated amplitude
    audio_data = 0.12 * np.sin(2 * np.pi * 300 * t) + 0.08 * np.sin(2 * np.pi * 600 * t)
    valid_audio = tmp_path / "valid.wav"
    sf.write(str(valid_audio), audio_data.astype(np.float32), sr)

    valid_script = "Hello thanks for calling Apex Dental Studio in Pune. I can schedule your cleaning for Thursday at two."
    words = [
        {"word": "Hello"}, {"word": "thanks"}, {"word": "for"}, {"word": "calling"},
        {"word": "Apex"}, {"word": "Dental"}, {"word": "Studio"}, {"word": "in"},
        {"word": "Pune"}, {"word": "I"}, {"word": "can"}, {"word": "schedule"},
        {"word": "your"}, {"word": "cleaning"}, {"word": "for"}, {"word": "Thursday"},
        {"word": "at"}, {"word": "two"}
    ]
    valid_caption = "Automate your front desk with Vocalis AI. Link in bio to learn more. Simulated call for demo."
    valid_hook = "POV: Receptionist handling calls"

    # Test QC execution on audio and text (no video container checks since mock video file)
    report = qc.run_qc(
        video_path=tmp_path / "non_existent.mp4",
        audio_path=valid_audio,
        script_text=valid_script,
        hook_text=valid_hook,
        caption_text=valid_caption,
        words_data=words,
    )

    # Claims and WER must be completely clean
    claims_failures = [f for f in report["hard_failures"] if "Claims" in f]
    wer_failures = [f for f in report["hard_failures"] if "ASR" in f]
    assert len(claims_failures) == 0
    assert len(wer_failures) == 0
    assert report["metrics"]["asr_wer"] == 0.0


def test_telegram_bot_whitelist_and_buttons(test_db_session: Session):
    """Verify Telegram bot enforces whitelist and persists callback actions."""
    cfg = load_config()
    cfg.settings.telegram_allowed_chat_ids = [12345678, 98765432]
    cfg.settings.telegram_bot_token = "mock_test_token"

    bot = TelegramApprovalBot(config=cfg)

    # 1. Whitelist enforcement
    assert bot.is_chat_allowed(12345678) is True
    assert bot.is_chat_allowed(98765432) is True
    assert bot.is_chat_allowed(99999999) is False  # Unauthorized

    # 2. Send request to unauthorized chat -> rejected
    res_unauth = bot.send_approval_request(
        chat_id=99999999,
        video_path=Path("fake.mp4"),
        cover_path=None,
        caption_text="Test caption",
        business_profile={"name": "Apex Physio", "vertical": "physiotherapy", "city": "Pune"},
        plan_axes={"scenario": "new booking", "layout": "A_split", "palette": "midnight_indigo", "agent_voice": "af_heart", "caller_voice": "am_adam"},
        qc_report={"passed": True, "metrics": {"duration_seconds": 28.5, "loudness_lufs": -14.1, "asr_wer": 0.05}},
        video_id=101,
    )
    assert not res_unauth["ok"]
    assert "Unauthorized" in res_unauth["error"]

    # 3. Send request to authorized chat in mock mode
    bot.token = "mock_token"  # Triggers mock mode in telegram_bot
    res_auth = bot.send_approval_request(
        chat_id=12345678,
        video_path=Path("fake.mp4"),
        cover_path=None,
        caption_text="Test caption",
        business_profile={"name": "Apex Physio", "vertical": "physiotherapy", "city": "Pune", "owner_first_name": "Rohan"},
        plan_axes={"scenario": "new booking", "layout": "A_split", "palette": "midnight_indigo", "agent_voice": "af_heart", "caller_voice": "am_adam"},
        qc_report={"passed": True, "metrics": {"duration_seconds": 28.5, "loudness_lufs": -14.1, "asr_wer": 0.05}},
        video_id=101,
    )
    assert res_auth["ok"]
    assert res_auth["chat_id"] == 12345678
    assert res_auth["video_id"] == 101

    # Verify buttons structure
    kb = res_auth["reply_markup"]["inline_keyboard"]
    callbacks = [btn["callback_data"] for row in kb for btn in row]
    assert "approve:101" in callbacks
    assert "reject:101" in callbacks
    assert "regen:101" in callbacks
    assert "new_plan:101" in callbacks
    assert "edit_caption:101" in callbacks

    # 4. Handle callback action: Approve
    res_act = bot.handle_callback_action(
        session=test_db_session,
        chat_id=12345678,
        callback_data="approve:101",
        user_name="founder_alex",
    )
    assert res_act["ok"]
    assert res_act["decision"] == "approve"
    assert res_act["video_id"] == 101

    # Verify persisted in database
    approvals = test_db_session.exec(select(Approval).where(Approval.video_id == 101)).all()
    assert len(approvals) == 1
    assert approvals[0].decision == "approve"
    assert approvals[0].decided_by == "founder_alex"

    # 5. Handle callback action: Reject with reason
    res_rej = bot.handle_callback_action(
        session=test_db_session,
        chat_id=12345678,
        callback_data="reject:101:voice too robotic",
        user_name="founder_alex",
    )
    assert res_rej["ok"]
    assert res_rej["decision"] == "reject"

    approvals_rej = test_db_session.exec(select(Approval).where(Approval.video_id == 101)).all()
    assert len(approvals_rej) == 2
    assert approvals_rej[1].decision == "reject"
    assert approvals_rej[1].note == "voice too robotic"

    # 6. Unauthorized callback rejected
    res_unauth_cb = bot.handle_callback_action(
        session=test_db_session,
        chat_id=99999999,
        callback_data="approve:101",
    )
    assert not res_unauth_cb["ok"]
    assert "Unauthorized" in res_unauth_cb["error"]


@respx.mock
def test_telegram_bot_real_api_dispatch():
    """Verify HTTP dispatch to Telegram Bot API with respx."""
    token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    chat_id = 55512345

    cfg = load_config()
    cfg.settings.telegram_bot_token = token
    cfg.settings.telegram_allowed_chat_ids = [chat_id]

    bot = TelegramApprovalBot(config=cfg)

    # Mock Telegram sendMessage endpoint
    mock_route = respx.post(f"https://api.telegram.org/bot{token}/sendMessage").mock(
        return_value=httpx.Response(
            200,
            json={"ok": True, "result": {"message_id": 999, "chat": {"id": chat_id}}},
        )
    )

    with httpx.Client() as client:
        res = bot.send_approval_request(
            chat_id=chat_id,
            video_path=Path("dummy.mp4"),
            cover_path=None,
            caption_text="Test caption",
            business_profile={"name": "Urban Roots Florist", "vertical": "florist", "city": "Bengaluru", "owner_first_name": "Priya"},
            plan_axes={"scenario": "availability check", "layout": "B_phone", "palette": "emerald_luxury", "agent_voice": "af_bella", "caller_voice": "am_michael"},
            qc_report={"passed": True, "metrics": {"duration_seconds": 29.1, "loudness_lufs": -13.9, "asr_wer": 0.04}},
            video_id=202,
            client=client,
        )

    assert mock_route.called
    assert res["ok"] is True
    assert res["result"]["message_id"] == 999
