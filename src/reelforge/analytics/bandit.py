"""Multi-Armed Bandit optimization with Thompson Sampling and exploration floor.
Optimizes high-dimensional video axes: vertical, hook_style, scenario, layout.
Enforces:
1. Permanent exploration floor: at least 30% of picks ignore performance priors.
2. Initial exploration phase: uniform priors when published count < 15.
3. Cooldown rules strictly override the bandit sampler.
"""
from datetime import datetime, timezone
import logging
import random
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from sqlmodel import Session, select

from reelforge.config import ReelForgeConfig, load_config
from reelforge.models import BanditStat

logger = logging.getLogger(__name__)


class ThompsonBandit:
    def __init__(self, config: Optional[ReelForgeConfig] = None):
        self.config = config or load_config()
        self.exploration_floor = 0.30  # Hard requirement: >= 30% exploration floor
        self.min_published_for_exploitation = 15

    def get_arm_stats(self, session: Session, arm_key: str) -> Tuple[float, float, int]:
        """Fetch (alpha, beta, n) for a given arm from SQLite."""
        record = session.exec(select(BanditStat).where(BanditStat.arm_key == arm_key)).first()
        if record:
            return record.alpha, record.beta, record.n
        return 1.0, 1.0, 0  # Uniform prior Beta(1, 1)

    def update_arm(
        self,
        session: Session,
        arm_key: str,
        reward: float,  # Normalized in [0.0, 1.0]
    ) -> BanditStat:
        """Update Beta distribution priors based on normalized reward feedback."""
        record = session.exec(select(BanditStat).where(BanditStat.arm_key == arm_key)).first()
        reward = max(0.0, min(1.0, float(reward)))

        if not record:
            record = BanditStat(
                arm_key=arm_key,
                alpha=1.0 + reward,
                beta=1.0 + (1.0 - reward),
                n=1,
                updated_at=datetime.now(timezone.utc),
            )
            session.add(record)
        else:
            record.alpha += reward
            record.beta += (1.0 - reward)
            record.n += 1
            record.updated_at = datetime.now(timezone.utc)

        session.commit()
        session.refresh(record)
        return record

    def sample_best_arm(
        self,
        axis_name: str,
        candidate_values: List[str],
        session: Optional[Session] = None,
        total_published: int = 0,
        rng: Optional[random.Random] = None,
    ) -> str:
        """Select arm using Thompson sampling with permanent exploration floor."""
        if not candidate_values:
            raise ValueError("No candidate values provided to bandit.")

        r = rng or random.Random()

        # 1. Pure exploration during cold start (< 15 published videos)
        if total_published < self.min_published_for_exploitation or session is None:
            return r.choice(candidate_values)

        # 2. Permanent Exploration Floor: >= 30% of picks ignore priors
        if r.random() < self.exploration_floor:
            return r.choice(candidate_values)

        # 3. Thompson Sampling from Beta distributions
        best_arm = candidate_values[0]
        highest_sample = -1.0

        for val in candidate_values:
            arm_key = f"{axis_name}:{val}"
            alpha, beta, _ = self.get_arm_stats(session, arm_key)
            # Sample theta ~ Beta(alpha, beta)
            theta = float(np.random.beta(alpha, beta))
            if theta > highest_sample:
                highest_sample = theta
                best_arm = val

        return best_arm
