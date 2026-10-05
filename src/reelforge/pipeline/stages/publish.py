"""Stage 12 Instagram Publishing Stage for ReelForge.
Publishes video container, polls status, and records permalink.
"""
import logging
from typing import Any, Dict, Optional
import httpx
from sqlmodel import Session

from reelforge.config import ReelForgeConfig, load_config
from reelforge.social.instagram import InstagramPublisher

logger = logging.getLogger(__name__)


def run_publish_stage(
    video_id: int,
    video_url: str,
    caption: str,
    cover_url: Optional[str] = None,
    session: Optional[Session] = None,
    config: Optional[ReelForgeConfig] = None,
    client: Optional[httpx.Client] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Execute Stage 12: Instagram Reels Publishing."""
    publisher = InstagramPublisher(config=config, client=client)
    res = publisher.publish_reel(
        video_id=video_id,
        video_url=video_url,
        caption=caption,
        cover_url=cover_url,
        session=session,
        dry_run=dry_run,
    )
    logger.info(f"Publish stage completed for Video {video_id}: {res.get('permalink')}")
    return res
