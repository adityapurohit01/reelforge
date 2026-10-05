"""Layer 2 Cooldown constraints engine for ReelForge.
Enforces hard cooldown rules against past history and provides a deterministic relaxation cascade.
"""
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlmodel import Session, select

from reelforge.config import CooldownsConfig
from reelforge.models import Business, Plan, Video

logger = logging.getLogger(__name__)


@dataclass
class CooldownViolation:
    axis: str
    value: Any
    history_distance: int
    required_distance: int
    rule_name: str


class CooldownEngine:
    def __init__(self, config: Optional[CooldownsConfig] = None):
        self.config = config or CooldownsConfig()

    def get_past_history(self, session: Session, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch past plans and businesses in reverse chronological order."""
        statement = select(Plan).order_by(Plan.created_at.desc()).limit(limit)  # type: ignore
        past_plans = session.exec(statement).all()

        history = []
        for p in past_plans:
            try:
                axes = json.loads(p.axis_tuple_json)
                history.append(axes)
            except Exception as e:
                logger.warning(f"Could not parse axis_tuple_json for plan {p.id}: {e}")
        return history

    def get_past_business_names(self, session: Session) -> Set[str]:
        """Fetch all historical business names (normalized to lower case)."""
        statement = select(Business.name)
        names = session.exec(statement).all()
        return {n.strip().lower() for n in names if n}

    def check_candidate(
        self,
        candidate: Dict[str, Any],
        history: List[Dict[str, Any]],
        overrides: Optional[Dict[str, int]] = None,
    ) -> List[CooldownViolation]:
        """Check a candidate axis tuple against past history. Returns list of violations."""
        violations: List[CooldownViolation] = []
        cooldowns = overrides or {}

        def get_cd(key: str, default: int) -> int:
            return cooldowns.get(key, default)

        # 1. Vertical cooldown (default 5, never 2 consecutive)
        vert_cd = get_cd("vertical", self.config.vertical)
        candidate_vert = candidate.get("vertical")
        for dist, past in enumerate(history[:vert_cd], start=1):
            if past.get("vertical") == candidate_vert:
                violations.append(
                    CooldownViolation(
                        axis="vertical",
                        value=candidate_vert,
                        history_distance=dist,
                        required_distance=vert_cd,
                        rule_name="vertical_cooldown",
                    )
                )
                break

        # Hard invariant: vertical never repeated consecutively (distance 1)
        if history and history[0].get("vertical") == candidate_vert:
            violations.append(
                CooldownViolation(
                    axis="vertical",
                    value=candidate_vert,
                    history_distance=1,
                    required_distance=2,
                    rule_name="consecutive_vertical_forbidden",
                )
            )

        # 2. Locale city cooldown (default 6)
        city_cd = get_cd("city", self.config.city)
        candidate_city = candidate.get("city")
        for dist, past in enumerate(history[:city_cd], start=1):
            if past.get("city") == candidate_city:
                violations.append(
                    CooldownViolation(
                        axis="city",
                        value=candidate_city,
                        history_distance=dist,
                        required_distance=city_cd,
                        rule_name="city_cooldown",
                    )
                )
                break

        # 3. Scenario type cooldown (default 4)
        scen_cd = get_cd("scenario", self.config.scenario)
        candidate_scen = candidate.get("scenario")
        for dist, past in enumerate(history[:scen_cd], start=1):
            if past.get("scenario") == candidate_scen:
                violations.append(
                    CooldownViolation(
                        axis="scenario",
                        value=candidate_scen,
                        history_distance=dist,
                        required_distance=scen_cd,
                        rule_name="scenario_cooldown",
                    )
                )
                break

        # 4. Hook style cooldown (default 8)
        hook_cd = get_cd("hook_style", self.config.hook_style)
        candidate_hook = candidate.get("hook_style")
        for dist, past in enumerate(history[:hook_cd], start=1):
            if past.get("hook_style") == candidate_hook:
                violations.append(
                    CooldownViolation(
                        axis="hook_style",
                        value=candidate_hook,
                        history_distance=dist,
                        required_distance=hook_cd,
                        rule_name="hook_style_cooldown",
                    )
                )
                break

        # 5. Layout + Palette combo (default 6) & Palette alone (default 3)
        layout_pal_cd = get_cd("layout_palette", self.config.layout_palette)
        pal_alone_cd = get_cd("palette_alone", self.config.palette_alone)
        cand_layout = candidate.get("layout")
        cand_pal = candidate.get("palette")

        for dist, past in enumerate(history[:layout_pal_cd], start=1):
            if past.get("layout") == cand_layout and past.get("palette") == cand_pal:
                violations.append(
                    CooldownViolation(
                        axis="layout_palette",
                        value=f"{cand_layout}+{cand_pal}",
                        history_distance=dist,
                        required_distance=layout_pal_cd,
                        rule_name="layout_palette_combo_cooldown",
                    )
                )
                break

        for dist, past in enumerate(history[:pal_alone_cd], start=1):
            if past.get("palette") == cand_pal:
                violations.append(
                    CooldownViolation(
                        axis="palette",
                        value=cand_pal,
                        history_distance=dist,
                        required_distance=pal_alone_cd,
                        rule_name="palette_alone_cooldown",
                    )
                )
                break

        # 6. Voice pair cooldown (default 4) & Agent voice in last 5 (max 2)
        vp_cd = get_cd("voice_pair", self.config.voice_pair)
        cand_vp = candidate.get("voice_pair")
        cand_agent_voice = candidate.get("agent_voice")

        for dist, past in enumerate(history[:vp_cd], start=1):
            if past.get("voice_pair") == cand_vp:
                violations.append(
                    CooldownViolation(
                        axis="voice_pair",
                        value=cand_vp,
                        history_distance=dist,
                        required_distance=vp_cd,
                        rule_name="voice_pair_cooldown",
                    )
                )
                break

        agent_voice_max = self.config.agent_voice_max_in_5
        recent_5_agents = [p.get("agent_voice") for p in history[:5] if p.get("agent_voice")]
        if recent_5_agents.count(cand_agent_voice) >= agent_voice_max:
            violations.append(
                CooldownViolation(
                    axis="agent_voice",
                    value=cand_agent_voice,
                    history_distance=recent_5_agents.count(cand_agent_voice),
                    required_distance=agent_voice_max,
                    rule_name="agent_voice_frequency_limit",
                )
            )

        return violations

    def get_relaxation_sequence(self) -> List[Tuple[str, int, str]]:
        """Deterministic relaxation ladder when all permutations are exhausted."""
        return [
            ("palette_alone", 2, "Relaxed palette alone cooldown from 3 to 2"),
            ("voice_pair", 3, "Relaxed voice pair cooldown from 4 to 3"),
            ("layout_palette", 4, "Relaxed layout+palette combo from 6 to 4"),
            ("hook_style", 6, "Relaxed hook style cooldown from 8 to 6"),
            ("city", 4, "Relaxed locale city cooldown from 6 to 4"),
            ("scenario", 3, "Relaxed scenario cooldown from 4 to 3"),
            ("vertical", 3, "Relaxed vertical cooldown from 5 to 3"),
        ]
