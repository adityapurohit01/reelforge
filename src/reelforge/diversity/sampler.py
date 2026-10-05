"""Layer 4 Novelty-aware sampler with Thompson-sampling bandit feedback and exploration floor."""
import json
import math
import random
from typing import Any, Dict, List, Optional, Tuple
from sqlmodel import Session, select

from reelforge.diversity.cooldown import CooldownEngine
from reelforge.diversity.taxonomy import (
    BUSINESS_PERSONAS,
    CALLER_PERSONAS,
    CAPTION_STYLES,
    FONT_PAIRING_IDS,
    HOOK_TEMPLATES,
    LAYOUTS,
    LOCALES,
    MOTION_PROFILE_IDS,
    MUSIC_TRACKS,
    PALETTE_IDS,
    SCENARIO_TYPES,
    VERTICALS,
    VOICE_PAIRS,
)
from reelforge.models import BanditStat, PublishLog


class NoveltySampler:
    def __init__(self, cooldown_engine: Optional[CooldownEngine] = None, exploration_floor: float = 0.30):
        self.cooldown_engine = cooldown_engine or CooldownEngine()
        self.exploration_floor = exploration_floor

    def _get_lru_distance(self, axis: str, val: Any, history: List[Dict[str, Any]]) -> float:
        """Calculate least-recently-used distance for an axis value."""
        for idx, item in enumerate(history):
            if item.get(axis) == val:
                return float(idx + 1)
        return float(len(history) + 10)  # High score if never seen

    def _sample_bandit_prior(self, session: Optional[Session], arm_key: str, rng: random.Random) -> float:
        """Sample from Beta distribution prior for an arm key using Thompson Sampling."""
        if not session:
            return 0.5

        # Check total published videos count
        published_count = len(session.exec(select(PublishLog.id).where(PublishLog.status == "PUBLISHED")).all())
        if published_count < 15:
            # Pure exploration prior with fewer than 15 published videos
            return rng.uniform(0.4, 0.6)

        stat = session.get(BanditStat, arm_key)
        if not stat:
            # Standard uniform uninformative prior Beta(1, 1)
            alpha, beta = 1.0, 1.0
        else:
            alpha, beta = stat.alpha, stat.beta

        # Standard Thompson sampling from Beta(alpha, beta)
        # using Gamma variates
        gamma_a = rng.gammavariate(alpha, 1.0)
        gamma_b = rng.gammavariate(beta, 1.0)
        if gamma_a + gamma_b == 0:
            return 0.5
        return gamma_a / (gamma_a + gamma_b)

    def sample_plan(
        self,
        session: Optional[Session] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        seed: Optional[int] = None,
    ) -> Tuple[Dict[str, Any], List[str]]:
        """Sample a novel, cooldown-compliant axis combination. Returns (axis_dict, relaxations_used)."""
        rng = random.Random(seed if seed is not None else random.randint(1, 10_000_000))
        past_history = history if history is not None else (self.cooldown_engine.get_past_history(session) if session else [])

        # Check exploration mode: with probability >= exploration_floor, ignore performance prior
        is_pure_exploration = rng.random() < self.exploration_floor

        relaxations_used: List[str] = []
        active_overrides: Dict[str, int] = {}

        # Search for a feasible candidate
        max_attempts = 1000
        relaxation_ladder = self.cooldown_engine.get_relaxation_sequence()
        relaxation_idx = 0

        while True:
            for _ in range(max_attempts):
                # Sample random candidates across taxonomy
                v = rng.choice(VERTICALS)
                loc = rng.choice(LOCALES)
                scen = rng.choice(SCENARIO_TYPES)
                bp = rng.choice(BUSINESS_PERSONAS)
                cp = rng.choice(CALLER_PERSONAS)
                hook = rng.choice(HOOK_TEMPLATES)
                layout = rng.choice(LAYOUTS)
                palette = rng.choice(PALETTE_IDS)
                font = rng.choice(FONT_PAIRING_IDS)
                caption = rng.choice(CAPTION_STYLES)
                motion = rng.choice(MOTION_PROFILE_IDS)
                vp = rng.choice(VOICE_PAIRS)
                music = rng.choice(MUSIC_TRACKS)

                candidate = {
                    "vertical": v.id,
                    "vertical_name": v.name,
                    "city": loc.city,
                    "country": loc.country,
                    "currency_symbol": loc.currency_symbol,
                    "currency_code": loc.currency_code,
                    "phone_pattern": loc.phone_pattern,
                    "business_persona": bp["type"],
                    "caller_mood": cp["mood"],
                    "caller_relationship": cp["relationship"],
                    "scenario": scen["id"],
                    "scenario_name": scen["name"],
                    "target_outcome": scen["outcome"],
                    "hook_style": hook.id,
                    "hook_family": hook.family,
                    "layout": layout,
                    "palette": palette,
                    "font_pairing": font,
                    "caption_style": caption,
                    "motion_profile": motion,
                    "voice_pair": f"{vp['agent']}+{vp['caller']}",
                    "agent_voice": vp["agent"],
                    "caller_voice": vp["caller"],
                    "music_track": music,
                    "speed_jitter": round(rng.uniform(-0.06, 0.06), 3),
                    "phone_effect": rng.choice([True, False]),
                }

                # Evaluate hard cooldowns
                violations = self.cooldown_engine.check_candidate(candidate, past_history, active_overrides)
                if not violations:
                    # Calculate novelty score
                    dist_vert = self._get_lru_distance("vertical", candidate["vertical"], past_history)
                    dist_city = self._get_lru_distance("city", candidate["city"], past_history)
                    dist_scen = self._get_lru_distance("scenario", candidate["scenario"], past_history)
                    dist_hook = self._get_lru_distance("hook_style", candidate["hook_style"], past_history)
                    novelty = (dist_vert * 2.0) + (dist_city * 1.5) + (dist_scen * 1.5) + (dist_hook * 2.0)

                    if not is_pure_exploration and session:
                        # Incorporate Thompson sampling prior
                        prior_vert = self._sample_bandit_prior(session, f"vertical:{candidate['vertical']}", rng)
                        prior_hook = self._sample_bandit_prior(session, f"hook:{candidate['hook_style']}", rng)
                        score = novelty + 10.0 * (prior_vert + prior_hook)
                    else:
                        score = novelty

                    candidate["_selection_score"] = round(score, 2)
                    candidate["_is_pure_exploration"] = is_pure_exploration
                    return candidate, relaxations_used

            # If no combination satisfied constraints after max_attempts, step down relaxation ladder
            if relaxation_idx < len(relaxation_ladder):
                key, new_val, reason = relaxation_ladder[relaxation_idx]
                active_overrides[key] = new_val
                relaxations_used.append(reason)
                relaxation_idx += 1
            else:
                # Fallback: force unique vertical and city not equal to the most recent one
                candidate["vertical"] = [vert.id for vert in VERTICALS if not past_history or past_history[0].get("vertical") != vert.id][0]
                return candidate, relaxations_used
