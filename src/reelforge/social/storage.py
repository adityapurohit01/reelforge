"""Cloud & local storage backend interface for public media distribution.
Required for Meta Instagram Graph API which fetches video assets via public HTTPS URLs.
"""
from abc import ABC, abstractmethod
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from reelforge.config import ReelForgeConfig, load_config

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    @abstractmethod
    def upload(self, video_path: Path, cover_path: Optional[Path] = None) -> Dict[str, str]:
        """Upload video and optional cover image.
        Returns dict with 'video_url', 'cover_url', and 'object_keys'.
        """
        pass

    @abstractmethod
    def cleanup(self, object_keys: List[str]) -> bool:
        """Delete temporary objects after publishing."""
        pass


class R2Storage(StorageBackend):
    """Cloudflare R2 (S3-compatible API) storage provider via boto3."""

    def __init__(self, config: Optional[ReelForgeConfig] = None):
        self.config = config or load_config()
        self.settings = self.config.settings
        self.bucket = self.settings.r2_bucket or "reelforge-media"
        self.public_base_url = (self.settings.r2_public_base_url or "").rstrip("/")
        self.account_id = self.settings.r2_account_id or ""
        self.endpoint_url = f"https://{self.account_id}.r2.cloudflarestorage.com" if self.account_id else None

    def _get_client(self):
        import boto3
        from botocore.config import Config

        return boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.settings.r2_access_key_id,
            aws_secret_access_key=self.settings.r2_secret_access_key,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )

    def upload(self, video_path: Path, cover_path: Optional[Path] = None) -> Dict[str, str]:
        """Upload video and cover with randomized object keys."""
        s3 = self._get_client()
        unique_prefix = f"reels/{uuid.uuid4().hex}"
        object_keys = []

        # 1. Video Upload
        video_key = f"{unique_prefix}/{video_path.name}"
        s3.upload_file(
            str(video_path),
            self.bucket,
            video_key,
            ExtraArgs={"ContentType": "video/mp4"},
        )
        object_keys.append(video_key)
        video_url = f"{self.public_base_url}/{video_key}"

        # 2. Cover Upload
        cover_url = ""
        if cover_path and cover_path.exists():
            cover_key = f"{unique_prefix}/{cover_path.name}"
            content_type = "image/jpeg" if cover_path.suffix.lower() in [".jpg", ".jpeg"] else "image/png"
            s3.upload_file(
                str(cover_path),
                self.bucket,
                cover_key,
                ExtraArgs={"ContentType": content_type},
            )
            object_keys.append(cover_key)
            cover_url = f"{self.public_base_url}/{cover_key}"

        return {
            "video_url": video_url,
            "cover_url": cover_url,
            "object_keys": object_keys,
        }

    def cleanup(self, object_keys: List[str]) -> bool:
        """Remove objects from R2 bucket."""
        if not object_keys:
            return True
        try:
            s3 = self._get_client()
            delete_objects = [{"Key": k} for k in object_keys]
            s3.delete_objects(Bucket=self.bucket, Delete={"Objects": delete_objects})
            logger.info(f"Cleaned up {len(object_keys)} objects from R2 bucket {self.bucket}")
            return True
        except Exception as e:
            logger.warning(f"Failed to cleanup R2 objects: {e}")
            return False


class LocalMockStorage(StorageBackend):
    """Local mock storage for development, testing, and dry runs."""

    def __init__(self, base_url: str = "https://mock-cdn.reelforge.local"):
        self.base_url = base_url.rstrip("/")

    def upload(self, video_path: Path, cover_path: Optional[Path] = None) -> Dict[str, str]:
        unique_id = uuid.uuid4().hex[:12]
        video_key = f"mock_reels/{unique_id}/{video_path.name}"
        video_url = f"{self.base_url}/{video_key}"

        cover_url = ""
        object_keys = [video_key]
        if cover_path:
            cover_key = f"mock_reels/{unique_id}/{cover_path.name}"
            cover_url = f"{self.base_url}/{cover_key}"
            object_keys.append(cover_key)

        return {
            "video_url": video_url,
            "cover_url": cover_url,
            "object_keys": object_keys,
        }

    def cleanup(self, object_keys: List[str]) -> bool:
        logger.info(f"[Mock Storage] Cleaned up {len(object_keys)} mock objects.")
        return True


def get_storage_backend(config: Optional[ReelForgeConfig] = None) -> StorageBackend:
    """Factory function returning configured storage backend."""
    cfg = config or load_config()
    if cfg.settings.r2_account_id and cfg.settings.r2_access_key_id:
        return R2Storage(cfg)
    return LocalMockStorage()
