"""Stage 10 Telegram Approval Pipeline Stage for ReelForge.
Dispatches briefing to founder on Telegram, awaiting interactive inline button approval.
"""
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import httpx
from sqlmodel import Session

from reelforge.config import ReelForgeConfig, load_config
from reelforge.social.telegram_bot import TelegramApprovalBot

logger = logging.getLogger(__name__)


def run_approval_stage(
    chat_id: int,
    video_id: int,
    video_path: Path,
    cover_path: Optional[Path],
    caption_text: str,
    business_profile: Dict[str, Any],
    plan_axes: Dict[str, Any],
    qc_report: Dict[str, Any],
    config: Optional[ReelForgeConfig] = None,
    client: Optional[httpx.Client] = None,
) -> Dict[str, Any]:
    """Execute Stage 10: Dispatch approval briefing to Telegram."""
    bot = TelegramApprovalBot(config)
    res = bot.send_approval_request(
        chat_id=chat_id,
        video_path=video_path,
        cover_path=cover_path,
        caption_text=caption_text,
        business_profile=business_profile,
        plan_axes=plan_axes,
        qc_report=qc_report,
        video_id=video_id,
        client=client,
    )
    return res
