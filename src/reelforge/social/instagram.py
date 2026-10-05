"""Stage 12 Instagram Graph API Reels Publishing Module.
Adheres strictly to Meta official Graph API specifications:
- API host: https://graph.facebook.com/{GRAPH_API_VERSION}
- 3-step publishing flow: Container creation -> Processing status polling -> Media publish
- Idempotency & duplicate-publishing protection via SQLite publish_log
- Publishing quota checking (content_publishing_limit)
- Long-lived token refresh lifecycle
- Dry-run execution mode
"""
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple
import httpx
from sqlmodel import Session, select

from reelforge.config import ReelForgeConfig, load_config
from reelforge.models import PublishLog

logger = logging.getLogger(__name__)


class InstagramAPIError(Exception):
    def __init__(self, message: str, code: Optional[int] = None, subcode: Optional[int] = None):
        super().__init__(message)
        self.code = code
        self.subcode = subcode


class InstagramPublisher:
    def __init__(self, config: Optional[ReelForgeConfig] = None, client: Optional[httpx.Client] = None):
        self.config = config or load_config()
        self.settings = self.config.settings
        self.version = self.settings.graph_api_version or "v21.0"
        self.base_url = f"https://graph.facebook.com/{self.version}"
        self.ig_user_id = self.settings.ig_user_id or ""
        self.access_token = self.settings.ig_access_token or ""
        self.client = client or httpx.Client(timeout=60.0)

    def _check_credentials(self):
        if not self.ig_user_id or not self.access_token:
            raise InstagramAPIError("Missing IG_USER_ID or IG_ACCESS_TOKEN in configuration.")

    def check_quota(self) -> Dict[str, Any]:
        """Check remaining 24-hour publishing quota for the Instagram account."""
        self._check_credentials()
        url = f"{self.base_url}/{self.ig_user_id}/content_publishing_limit"
        params = {
            "fields": "quota_usage,config",
            "access_token": self.access_token,
        }
        resp = self.client.get(url, params=params)
        data = resp.json()
        if resp.status_code != 200 or "error" in data:
            err = data.get("error", {})
            raise InstagramAPIError(
                f"Quota check failed: {err.get('message', 'Unknown error')}",
                code=err.get("code"),
                subcode=err.get("error_subcode"),
            )

        items = data.get("data", [{}])
        info = items[0] if items else {}
        usage = info.get("quota_usage", 0)
        total = info.get("config", {}).get("quota_total", 50)
        return {
            "quota_usage": usage,
            "quota_total": total,
            "quota_remaining": max(0, total - usage),
        }

    def create_reel_container(
        self,
        video_url: str,
        caption: str,
        cover_url: Optional[str] = None,
        share_to_feed: bool = True,
    ) -> str:
        """Create media container for an Instagram Reel."""
        self._check_credentials()
        url = f"{self.base_url}/{self.ig_user_id}/media"
        payload = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true" if share_to_feed else "false",
            "access_token": self.access_token,
        }
        if cover_url:
            payload["cover_url"] = cover_url

        resp = self.client.post(url, data=payload)
        data = resp.json()
        if resp.status_code != 200 or "error" in data:
            err = data.get("error", {})
            raise InstagramAPIError(
                f"Container creation failed: {err.get('message', 'Unknown error')}",
                code=err.get("code"),
                subcode=err.get("error_subcode"),
            )

        container_id = data.get("id")
        if not container_id:
            raise InstagramAPIError("No container ID returned by Meta API.")
        return str(container_id)

    def poll_container_status(
        self,
        container_id: str,
        timeout_seconds: float = 600.0,
        initial_poll_interval: float = 5.0,
        max_poll_interval: float = 30.0,
    ) -> Tuple[str, Optional[str]]:
        """Poll container processing status until FINISHED, ERROR, EXPIRED, or timeout."""
        self._check_credentials()
        url = f"{self.base_url}/{container_id}"
        params = {
            "fields": "status_code,status",
            "access_token": self.access_token,
        }

        start_time = time.time()
        interval = initial_poll_interval

        while time.time() - start_time < timeout_seconds:
            resp = self.client.get(url, params=params)
            data = resp.json()
            if resp.status_code != 200 or "error" in data:
                err = data.get("error", {})
                raise InstagramAPIError(
                    f"Status check failed: {err.get('message', 'Unknown error')}",
                    code=err.get("code"),
                    subcode=err.get("error_subcode"),
                )

            status_code = data.get("status_code", "IN_PROGRESS").upper()
            status_desc = data.get("status", "")

            if status_code == "FINISHED":
                return "FINISHED", None
            elif status_code in ["ERROR", "EXPIRED"]:
                return status_code, status_desc or f"Container status reported {status_code}"

            time.sleep(interval)
            interval = min(max_poll_interval, interval * 1.5)

        return "TIMEOUT", f"Container processing timed out after {timeout_seconds:.0f} seconds."

    def publish_container(self, container_id: str) -> str:
        """Publish the processed media container to make the Reel live."""
        self._check_credentials()
        url = f"{self.base_url}/{self.ig_user_id}/media_publish"
        payload = {
            "creation_id": container_id,
            "access_token": self.access_token,
        }
        resp = self.client.post(url, data=payload)
        data = resp.json()
        if resp.status_code != 200 or "error" in data:
            err = data.get("error", {})
            raise InstagramAPIError(
                f"Publishing failed: {err.get('message', 'Unknown error')}",
                code=err.get("code"),
                subcode=err.get("error_subcode"),
            )

        media_id = data.get("id")
        if not media_id:
            raise InstagramAPIError("No media ID returned on publish.")
        return str(media_id)

    def get_media_permalink(self, media_id: str) -> str:
        """Fetch the public permalink for a published Reel."""
        self._check_credentials()
        url = f"{self.base_url}/{media_id}"
        params = {
            "fields": "permalink,timestamp",
            "access_token": self.access_token,
        }
        resp = self.client.get(url, params=params)
        data = resp.json()
        return data.get("permalink", f"https://www.instagram.com/reel/{media_id}")

    def refresh_long_lived_token(self) -> Dict[str, Any]:
        """Refresh a 60-day long-lived access token before expiration."""
        self._check_credentials()
        # For Instagram User access tokens
        url = "https://graph.instagram.com/refresh_access_token"
        params = {
            "grant_type": "ig_refresh_token",
            "access_token": self.access_token,
        }
        resp = self.client.get(url, params=params)
        data = resp.json()
        if resp.status_code != 200 or "error" in data:
            # Fallback to Facebook exchange token endpoint
            fb_url = f"{self.base_url}/oauth/access_token"
            fb_params = {
                "grant_type": "fb_exchange_token",
                "client_id": self.settings.meta_app_id,
                "client_secret": self.settings.meta_app_secret,
                "fb_exchange_token": self.access_token,
            }
            resp = self.client.get(fb_url, params=fb_params)
            data = resp.json()

        if "access_token" in data:
            return {
                "ok": True,
                "access_token": data["access_token"],
                "expires_in": data.get("expires_in", 5184000),  # 60 days in seconds
            }
        err = data.get("error", {})
        raise InstagramAPIError(
            f"Token refresh failed: {err.get('message', 'Unknown error')}",
            code=err.get("code"),
        )

    def publish_reel(
        self,
        video_id: int,
        video_url: str,
        caption: str,
        cover_url: Optional[str] = None,
        session: Optional[Session] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Complete publishing lifecycle with duplicate protection and DB state logging."""
        # 1. Idempotency Check: Prevent duplicate publishing
        if session:
            existing_log = session.exec(
                select(PublishLog).where(
                    PublishLog.video_id == video_id,
                    PublishLog.status == "PUBLISHED",
                )
            ).first()
            if existing_log:
                logger.warning(f"Video {video_id} is already published! Media ID: {existing_log.media_id}")
                return {
                    "ok": True,
                    "already_published": True,
                    "media_id": existing_log.media_id,
                    "permalink": existing_log.permalink,
                    "status": "PUBLISHED",
                }

        # 2. Dry run handling
        if dry_run:
            logger.info(f"[Dry Run] Simulating Instagram Reel publish for Video {video_id}")
            return {
                "ok": True,
                "dry_run": True,
                "video_id": video_id,
                "container_id": "dry_run_container_998877",
                "media_id": "dry_run_media_112233",
                "permalink": "https://www.instagram.com/reel/dry_run_preview",
                "status": "DRY_RUN_SUCCESS",
            }

        # 3. Quota check
        quota = self.check_quota()
        if quota["quota_remaining"] <= 0:
            raise InstagramAPIError(f"Publishing quota exhausted ({quota['quota_usage']}/{quota['quota_total']}).")

        # 4. Container Management: Check for existing unfinished container
        container_id = None
        log_entry = None
        if session:
            log_entry = session.exec(
                select(PublishLog).where(PublishLog.video_id == video_id)
            ).first()
            if log_entry and log_entry.container_id:
                container_id = log_entry.container_id

        if not container_id:
            container_id = self.create_reel_container(
                video_url=video_url,
                caption=caption,
                cover_url=cover_url,
            )
            if session:
                if not log_entry:
                    log_entry = PublishLog(
                        video_id=video_id,
                        container_id=container_id,
                        status="CONTAINER_CREATED",
                        attempts=1,
                    )
                    session.add(log_entry)
                else:
                    log_entry.container_id = container_id
                    log_entry.attempts += 1
                session.commit()
                session.refresh(log_entry)

        # 5. Poll container processing
        status, err_msg = self.poll_container_status(container_id)
        if status != "FINISHED":
            if session and log_entry:
                log_entry.status = f"FAILED_{status}"
                log_entry.error = err_msg
                session.commit()
            raise InstagramAPIError(f"Container processing failed ({status}): {err_msg}")

        # 6. Media Publish
        media_id = self.publish_container(container_id)
        permalink = self.get_media_permalink(media_id)

        # 7. Update DB state
        if session and log_entry:
            log_entry.status = "PUBLISHED"
            log_entry.media_id = media_id
            log_entry.permalink = permalink
            log_entry.published_at = datetime.now(timezone.utc)
            session.commit()

        return {
            "ok": True,
            "container_id": container_id,
            "media_id": media_id,
            "permalink": permalink,
            "status": "PUBLISHED",
        }
