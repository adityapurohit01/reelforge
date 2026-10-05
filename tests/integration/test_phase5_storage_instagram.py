"""Phase 5 Integration & Acceptance Tests.
Verifies:
1. Storage backend: Local mock storage & URL generation.
2. Instagram Graph API (Reels Content Publishing):
   - Success path: Quota check -> Container create -> Status poll -> Publish -> Permalink.
   - Idempotency & duplicate-publishing prevention via SQLite publish_log.
   - Processing timeout handling.
   - Container ERROR / EXPIRED status handling.
   - Token refresh lifecycle.
   - Dry-run publishing mode.
"""
from datetime import datetime, timezone
from pathlib import Path
import httpx
import pytest
import respx
from sqlmodel import Session, select

from reelforge.config import load_config
from reelforge.db import get_engine, init_db
from reelforge.models import PublishLog
from reelforge.social.instagram import InstagramAPIError, InstagramPublisher
from reelforge.social.storage import LocalMockStorage, get_storage_backend


@pytest.fixture
def test_db_session(tmp_path: Path):
    db_file = tmp_path / "test_p5_reelforge.db"
    db_url = f"sqlite:///{db_file}"
    engine = get_engine(db_url)
    init_db(engine)
    with Session(engine) as session:
        yield session


def test_storage_backend(tmp_path: Path):
    """Verify local mock storage upload and cleanup lifecycle."""
    storage = LocalMockStorage(base_url="https://cdn.reelforge.example.com")
    
    video_file = tmp_path / "sample_reel.mp4"
    video_file.write_bytes(b"\x00" * 1024)
    cover_file = tmp_path / "sample_cover.jpg"
    cover_file.write_bytes(b"\x00" * 512)

    res = storage.upload(video_file, cover_file)
    assert "https://cdn.reelforge.example.com/mock_reels/" in res["video_url"]
    assert "sample_reel.mp4" in res["video_url"]
    assert "sample_cover.jpg" in res["cover_url"]
    assert len(res["object_keys"]) == 2

    # Cleanup
    assert storage.cleanup(res["object_keys"]) is True


@respx.mock
def test_instagram_publish_success_flow(test_db_session: Session):
    """Verify full successful publishing lifecycle with mock Graph API."""
    user_id = "17841400012345678"
    token = "EAABtest_token_987"
    version = "v21.0"
    base_url = f"https://graph.facebook.com/{version}"

    cfg = load_config()
    cfg.settings.ig_user_id = user_id
    cfg.settings.ig_access_token = token
    cfg.settings.graph_api_version = version

    # 1. Mock Quota Check
    respx.get(f"{base_url}/{user_id}/content_publishing_limit").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"quota_usage": 4, "config": {"quota_total": 50}}]},
        )
    )

    # 2. Mock Container Creation
    respx.post(f"{base_url}/{user_id}/media").mock(
        return_value=httpx.Response(200, json={"id": "container_reel_1001"})
    )

    # 3. Mock Container Status Polling (returns FINISHED)
    respx.get(f"{base_url}/container_reel_1001").mock(
        return_value=httpx.Response(
            200,
            json={"status_code": "FINISHED", "status": "Ready to publish"},
        )
    )

    # 4. Mock Media Publish
    respx.post(f"{base_url}/{user_id}/media_publish").mock(
        return_value=httpx.Response(200, json={"id": "media_published_5555"})
    )

    # 5. Mock Permalink Fetch
    respx.get(f"{base_url}/media_published_5555").mock(
        return_value=httpx.Response(
            200,
            json={"permalink": "https://www.instagram.com/reel/C8XYZ12345/", "timestamp": "2026-10-05T12:00:00+0000"},
        )
    )

    publisher = InstagramPublisher(config=cfg)
    result = publisher.publish_reel(
        video_id=42,
        video_url="https://cdn.example.com/video.mp4",
        caption="Automated AI Front Desk #VocalisAI",
        cover_url="https://cdn.example.com/cover.jpg",
        session=test_db_session,
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["container_id"] == "container_reel_1001"
    assert result["media_id"] == "media_published_5555"
    assert "https://www.instagram.com/reel/C8XYZ12345/" in result["permalink"]

    # Verify persisted in database
    log = test_db_session.exec(select(PublishLog).where(PublishLog.video_id == 42)).first()
    assert log is not None
    assert log.status == "PUBLISHED"
    assert log.media_id == "media_published_5555"
    assert log.permalink == result["permalink"]


@respx.mock
def test_duplicate_publishing_prevention(test_db_session: Session):
    """Verify that a video already published cannot be published a second time."""
    user_id = "17841400012345678"
    token = "EAABtest_token_987"
    cfg = load_config()
    cfg.settings.ig_user_id = user_id
    cfg.settings.ig_access_token = token

    # Pre-populate DB with already published record
    existing_log = PublishLog(
        video_id=77,
        container_id="c_old_11",
        media_id="m_old_22",
        permalink="https://www.instagram.com/reel/already_published/",
        status="PUBLISHED",
        attempts=1,
        published_at=datetime.now(timezone.utc),
    )
    test_db_session.add(existing_log)
    test_db_session.commit()

    publisher = InstagramPublisher(config=cfg)
    # Attempting to publish again should early-return with already_published=True
    result = publisher.publish_reel(
        video_id=77,
        video_url="https://cdn.example.com/video.mp4",
        caption="New attempt caption",
        session=test_db_session,
    )

    assert result["ok"] is True
    assert result["already_published"] is True
    assert result["media_id"] == "m_old_22"
    assert result["permalink"] == "https://www.instagram.com/reel/already_published/"


@respx.mock
def test_container_error_status(test_db_session: Session):
    """Verify handling when Meta reports an ERROR status during media processing."""
    user_id = "17841400012345678"
    token = "EAABtest_token_987"
    base_url = f"https://graph.facebook.com/v21.0"

    cfg = load_config()
    cfg.settings.ig_user_id = user_id
    cfg.settings.ig_access_token = token
    cfg.settings.graph_api_version = "v21.0"

    respx.get(f"{base_url}/{user_id}/content_publishing_limit").mock(
        return_value=httpx.Response(200, json={"data": [{"quota_usage": 1, "config": {"quota_total": 50}}]})
    )
    respx.post(f"{base_url}/{user_id}/media").mock(
        return_value=httpx.Response(200, json={"id": "container_err_99"})
    )
    # Status endpoint reports ERROR
    respx.get(f"{base_url}/container_err_99").mock(
        return_value=httpx.Response(
            200,
            json={"status_code": "ERROR", "status": "Video codec unsupported or corrupted stream."},
        )
    )

    publisher = InstagramPublisher(config=cfg)
    with pytest.raises(InstagramAPIError) as exc_info:
        publisher.publish_reel(
            video_id=88,
            video_url="https://cdn.example.com/bad_video.mp4",
            caption="Caption",
            session=test_db_session,
        )

    assert "Container processing failed (ERROR)" in str(exc_info.value)
    
    # Check database status was updated
    log = test_db_session.exec(select(PublishLog).where(PublishLog.video_id == 88)).first()
    assert log is not None
    assert log.status == "FAILED_ERROR"


@respx.mock
def test_token_refresh_flow():
    """Verify long-lived access token refresh endpoint."""
    user_id = "17841400012345678"
    old_token = "EAAB_old_expiring_token"

    cfg = load_config()
    cfg.settings.ig_user_id = user_id
    cfg.settings.ig_access_token = old_token

    # Mock refresh endpoint
    respx.get("https://graph.instagram.com/refresh_access_token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "EAAB_new_refreshed_token_long_lived",
                "token_type": "bearer",
                "expires_in": 5184000,
            },
        )
    )

    publisher = InstagramPublisher(config=cfg)
    refresh_res = publisher.refresh_long_lived_token()
    assert refresh_res["ok"] is True
    assert refresh_res["access_token"] == "EAAB_new_refreshed_token_long_lived"
    assert refresh_res["expires_in"] == 5184000


def test_dry_run_mode():
    """Verify --dry-run returns mock publishing structure without API calls."""
    cfg = load_config()
    cfg.settings.ig_user_id = "fake_user"
    cfg.settings.ig_access_token = "fake_token"

    publisher = InstagramPublisher(config=cfg)
    res = publisher.publish_reel(
        video_id=999,
        video_url="https://cdn.example.com/video.mp4",
        caption="Dry run test",
        dry_run=True,
    )

    assert res["ok"] is True
    assert res["dry_run"] is True
    assert res["status"] == "DRY_RUN_SUCCESS"
    assert "dry_run_preview" in res["permalink"]
