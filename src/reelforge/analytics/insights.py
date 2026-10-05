"""Stage 13 Instagram Reels Insights Collection & Learning.
Pulls engagement metrics for published videos at 24h, 72h, and 7d intervals.
Updates SQLite metrics table and feeds normalized reward into Thompson bandit arms.
"""
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
import httpx
from sqlmodel import Session, select

from reelforge.analytics.bandit import ThompsonBandit
from reelforge.config import ReelForgeConfig, load_config
from reelforge.models import Metric, PublishLog, Video

logger = logging.getLogger(__name__)


class InsightsCollector:
    def __init__(self, config: Optional[ReelForgeConfig] = None, client: Optional[httpx.Client] = None):
        self.config = config or load_config()
        self.settings = self.config.settings
        self.version = self.settings.graph_api_version or "v21.0"
        self.base_url = f"https://graph.facebook.com/{self.version}"
        self.access_token = self.settings.ig_access_token or ""
        self.client = client or httpx.Client(timeout=30.0)
        self.bandit = ThompsonBandit(self.config)

    def fetch_reels_insights(self, media_id: str) -> Dict[str, Any]:
        """Fetch Reels metrics from Meta Graph API."""
        if not self.access_token or self.access_token.startswith("mock"):
            # Return realistic simulated insights for test/dev
            return {
                "reach": 1540,
                "views": 2180,
                "likes": 84,
                "comments": 12,
                "saves": 38,
                "shares": 25,
                "avg_watch_time_s": 22.4,
            }

        url = f"{self.base_url}/{media_id}/insights"
        # Meta Reels metric fields
        params = {
            "metric": "reach,plays,likes,comments,saved,shares,total_interactions",
            "access_token": self.access_token,
        }
        resp = self.client.get(url, params=params)
        data = resp.json()
        metrics = {
            "reach": 0,
            "views": 0,
            "likes": 0,
            "comments": 0,
            "saves": 0,
            "shares": 0,
            "avg_watch_time_s": 0.0,
        }
        for item in data.get("data", []):
            name = item.get("name")
            values = item.get("values", [{}])
            val = values[0].get("value", 0) if values else 0
            if name == "reach":
                metrics["reach"] = int(val)
            elif name in ["plays", "views"]:
                metrics["views"] = int(val)
            elif name == "likes":
                metrics["likes"] = int(val)
            elif name == "comments":
                metrics["comments"] = int(val)
            elif name == "saved":
                metrics["saves"] = int(val)
            elif name == "shares":
                metrics["shares"] = int(val)

        return metrics

    def compute_composite_reward(self, raw_metrics: Dict[str, Any]) -> float:
        """Compute normalized reward in [0.0, 1.0] giving higher weight to high-intent actions.
        Weighted Formula: (3*saves + 2*shares + likes + 2*comments) / max(views, 50).
        """
        views = max(raw_metrics.get("views", 0), 50)
        saves = raw_metrics.get("saves", 0)
        shares = raw_metrics.get("shares", 0)
        likes = raw_metrics.get("likes", 0)
        comments = raw_metrics.get("comments", 0)

        raw_score = (3.0 * saves + 2.0 * shares + likes + 2.0 * comments) / float(views)
        # Normalize into [0.0, 1.0] where 15% high-intent engagement is considered a 1.0 reward
        normalized = min(1.0, raw_score / 0.15)
        return round(normalized, 4)

    def process_video_metrics(
        self,
        session: Session,
        video_id: int,
        window: str = "24h",
        media_id: Optional[str] = None,
        axes_dict: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fetch insights, save in metrics table, and update bandit arms."""
        if not media_id:
            pub_log = session.exec(select(PublishLog).where(PublishLog.video_id == video_id)).first()
            if not pub_log or not pub_log.media_id:
                raise ValueError(f"No media_id found for Video {video_id}")
            media_id = pub_log.media_id

        raw = self.fetch_reels_insights(media_id)
        reward = self.compute_composite_reward(raw)

        # 1. Store in metrics table
        metric_rec = Metric(
            video_id=video_id,
            window=window,
            reach=raw.get("reach", 0),
            views=raw.get("views", 0),
            likes=raw.get("likes", 0),
            comments=raw.get("comments", 0),
            saves=raw.get("saves", 0),
            shares=raw.get("shares", 0),
            avg_watch_time_s=raw.get("avg_watch_time_s", 0.0),
            fetched_at=datetime.now(timezone.utc),
        )
        session.add(metric_rec)
        session.commit()

        # 2. Update Thompson Bandit arms if axes are provided
        if axes_dict:
            for axis in ["vertical", "hook_style", "scenario", "layout"]:
                val = axes_dict.get(axis)
                if val:
                    arm_key = f"{axis}:{val}"
                    self.bandit.update_arm(session, arm_key, reward)

        return {
            "video_id": video_id,
            "window": window,
            "metrics": raw,
            "composite_reward": reward,
        }
