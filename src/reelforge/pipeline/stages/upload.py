"""Stage 11 Media Upload Stage for ReelForge.
Uploads rendered MP4 and cover image to public storage (R2/S3) so Meta API can ingest them.
"""
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from reelforge.config import ReelForgeConfig, load_config
from reelforge.social.storage import get_storage_backend

logger = logging.getLogger(__name__)


def run_upload_stage(
    video_path: Path,
    cover_path: Optional[Path] = None,
    config: Optional[ReelForgeConfig] = None,
) -> Dict[str, Any]:
    """Upload media to cloud storage and return public URLs."""
    backend = get_storage_backend(config)
    res = backend.upload(video_path, cover_path)
    logger.info(f"Uploaded video to public URL: {res['video_url']}")
    return res
