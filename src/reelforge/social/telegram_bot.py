"""Stage 10 Telegram Founder Approval Bot.
Sends generated Reel, cover frame, QC report, and proposed caption to the founder
with interactive inline buttons: Approve, Reject, Regenerate, New Plan, Edit Caption.
Enforces strict chat-ID whitelisting.
"""
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import httpx
from sqlmodel import Session

from reelforge.config import ReelForgeConfig, load_config
from reelforge.models import Approval, Video

logger = logging.getLogger(__name__)


class TelegramApprovalBot:
    def __init__(self, config: Optional[ReelForgeConfig] = None):
        self.config = config or load_config()
        self.token = self.config.settings.telegram_bot_token or ""
        self.allowed_chats = self.config.settings.telegram_allowed_chat_ids
        self.api_base = f"https://api.telegram.org/bot{self.token}"

    def is_chat_allowed(self, chat_id: int) -> bool:
        """Check if incoming chat ID is strictly whitelisted."""
        if not self.allowed_chats:
            return False
        if isinstance(self.allowed_chats, str):
            try:
                parsed = json.loads(self.allowed_chats)
                if isinstance(parsed, list):
                    return int(chat_id) in [int(x) for x in parsed]
            except Exception:
                pass
            return str(chat_id) in [s.strip() for s in self.allowed_chats.replace("[", "").replace("]", "").split(",") if s.strip()]
        if isinstance(self.allowed_chats, (list, tuple, set)):
            return int(chat_id) in [int(x) for x in self.allowed_chats]
        return int(chat_id) == int(self.allowed_chats)

    def format_approval_message(
        self,
        business_profile: Dict[str, Any],
        plan_axes: Dict[str, Any],
        qc_report: Dict[str, Any],
        caption: str,
        video_id: int,
    ) -> str:
        """Format founder approval briefing in Telegram Markdown."""
        qc_status = "PASSED" if qc_report.get("passed", False) else "FAILED"
        qc_icon = "SUCCESS" if qc_status == "PASSED" else "FAIL"

        metrics = qc_report.get("metrics", {})
        dur = metrics.get("duration_seconds", 0.0)
        lufs = metrics.get("loudness_lufs", -14.0)
        wer = metrics.get("asr_wer", 0.0)

        lines = [
            f"🎬 *ReelForge Generation Approval — Video #{video_id}*",
            "",
            f"🏢 *Business:* {business_profile.get('name')} ({business_profile.get('vertical')})",
            f"📍 *Location:* {business_profile.get('city')} | Owner: {business_profile.get('owner_first_name')}",
            f"🎯 *Scenario:* {plan_axes.get('scenario')} | *Layout:* {plan_axes.get('layout')}",
            f"🎨 *Palette:* {plan_axes.get('palette')} | *Voices:* {plan_axes.get('agent_voice')} / {plan_axes.get('caller_voice')}",
            "",
            f"🛡️ *Quality Gate:* [{qc_icon}] *{qc_status}*",
            f"⏱️ Duration: {dur:.1f}s | 🔊 Loudness: {lufs:.1f} LUFS | 🎯 ASR WER: {wer:.1%}",
        ]

        soft_warnings = qc_report.get("soft_warnings", [])
        if soft_warnings:
            lines.append("⚠️ *Warnings:*")
            for w in soft_warnings:
                lines.append(f"  • {w}")

        lines.extend([
            "",
            "📝 *Proposed Instagram Caption:*",
            f"_{caption[:350]}..._" if len(caption) > 350 else f"_{caption}_",
            "",
            "👉 Please review and select an action below:",
        ])

        return "\n".join(lines)

    def get_approval_keyboard(self, video_id: int) -> Dict[str, Any]:
        """Construct inline action buttons."""
        return {
            "inline_keyboard": [
                [
                    {"text": "✅ Approve & Publish", "callback_data": f"approve:{video_id}"},
                    {"text": "❌ Reject", "callback_data": f"reject:{video_id}"},
                ],
                [
                    {"text": "🔄 Regenerate (Same Biz)", "callback_data": f"regen:{video_id}"},
                    {"text": "🆕 New Video (New Plan)", "callback_data": f"new_plan:{video_id}"},
                ],
                [
                    {"text": "✏️ Edit Caption", "callback_data": f"edit_caption:{video_id}"},
                ],
            ]
        }

    def send_approval_request(
        self,
        chat_id: int,
        video_path: Path,
        cover_path: Optional[Path],
        caption_text: str,
        business_profile: Dict[str, Any],
        plan_axes: Dict[str, Any],
        qc_report: Dict[str, Any],
        video_id: int,
        client: Optional[httpx.Client] = None,
    ) -> Dict[str, Any]:
        """Send video briefing to whitelisted Telegram chat."""
        if not self.is_chat_allowed(chat_id):
            logger.warning(f"Unauthorized chat_id {chat_id} attempted approval request")
            return {"ok": False, "error": "Unauthorized chat ID"}

        msg_text = self.format_approval_message(
            business_profile=business_profile,
            plan_axes=plan_axes,
            qc_report=qc_report,
            caption=caption_text,
            video_id=video_id,
        )
        reply_markup = self.get_approval_keyboard(video_id)

        # Dry run / mock mode if token is not provided
        if not self.token or self.token == "mock_token":
            logger.info(f"[Mock Telegram] Sent approval request to {chat_id} for Video #{video_id}")
            return {
                "ok": True,
                "mock": True,
                "chat_id": chat_id,
                "video_id": video_id,
                "message": msg_text,
                "reply_markup": reply_markup,
            }

        # Real Telegram Bot API Call
        cli = client or httpx.Client(timeout=60.0)
        try:
            # 1. Send text message with buttons
            resp = cli.post(
                f"{self.api_base}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": msg_text,
                    "parse_mode": "Markdown",
                    "reply_markup": reply_markup,
                },
            )
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to dispatch Telegram approval: {e}")
            return {"ok": False, "error": str(e)}

    def handle_callback_action(
        self,
        session: Session,
        chat_id: int,
        callback_data: str,
        user_name: str = "founder",
    ) -> Dict[str, Any]:
        """Handle incoming button clicks and persist decision in SQLite."""
        if not self.is_chat_allowed(chat_id):
            return {"ok": False, "error": "Unauthorized chat ID"}

        parts = callback_data.split(":")
        action = parts[0]
        video_id = int(parts[1]) if len(parts) > 1 else 0
        note = parts[2] if len(parts) > 2 else ""

        approval = Approval(
            video_id=video_id,
            decision=action,
            decided_by=user_name,
            decided_at=datetime.now(timezone.utc),
            note=note,
        )
        session.add(approval)
        session.commit()
        session.refresh(approval)

        return {
            "ok": True,
            "decision": action,
            "video_id": video_id,
            "approval_id": approval.id,
        }
