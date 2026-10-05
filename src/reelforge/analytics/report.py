"""Reporting module for diversity analytics, axis histograms, and performance insights.
Generates human-readable summaries and ASCII tables for CLI commands.
"""
from collections import Counter
import json
import logging
from typing import Any, Dict, List, Optional
from sqlmodel import Session, select

from reelforge.models import BanditStat, Metric, Plan, Video

logger = logging.getLogger(__name__)


def generate_diversity_report(session: Session, last_n: int = 30) -> str:
    """Generate structured diversity audit across the last N plans."""
    plans = session.exec(select(Plan).order_by(Plan.created_at.desc()).limit(last_n)).all()
    if not plans:
        return "No generation history available yet. Run `reelforge run` or `reelforge plan` to generate videos."

    total_records = len(plans)
    verticals = []
    cities = []
    layouts = []
    palettes = []
    scenarios = []
    hook_styles = []
    agent_voices = []

    for p in reversed(plans):
        try:
            axes = json.loads(p.axis_tuple_json)
            verticals.append(axes.get("vertical", "unknown"))
            cities.append(axes.get("city", "unknown"))
            layouts.append(axes.get("layout", "unknown"))
            palettes.append(axes.get("palette", "unknown"))
            scenarios.append(axes.get("scenario", "unknown"))
            hook_styles.append(axes.get("hook_style", "unknown"))
            agent_voices.append(axes.get("agent_voice", "unknown"))
        except Exception:
            continue

    def max_repeat_streak(items: List[str]) -> int:
        if not items:
            return 0
        max_streak = 1
        curr_streak = 1
        for i in range(1, len(items)):
            if items[i] == items[i - 1]:
                curr_streak += 1
                max_streak = max(max_streak, curr_streak)
            else:
                curr_streak = 1
        return max_streak

    lines = [
        "=" * 60,
        f"📊 REELFORGE DIVERSITY AUDIT REPORT (Last {total_records} Videos)",
        "=" * 60,
        "",
        "🎯 AXIS COVERAGE & UNIQUE COUNTS:",
        f"  • Verticals:   {len(set(verticals)):2d} unique across {total_records} runs (Max streak: {max_repeat_streak(verticals)})",
        f"  • Cities:      {len(set(cities)):2d} unique across {total_records} runs (Max streak: {max_repeat_streak(cities)})",
        f"  • Layouts:     {len(set(layouts)):2d} unique across {total_records} runs (Max streak: {max_repeat_streak(layouts)})",
        f"  • Palettes:    {len(set(palettes)):2d} unique across {total_records} runs (Max streak: {max_repeat_streak(palettes)})",
        f"  • Scenarios:   {len(set(scenarios)):2d} unique across {total_records} runs (Max streak: {max_repeat_streak(scenarios)})",
        f"  • Hook Styles: {len(set(hook_styles)):2d} unique across {total_records} runs (Max streak: {max_repeat_streak(hook_styles)})",
        f"  • Agent Voices:{len(set(agent_voices)):2d} unique across {total_records} runs (Max streak: {max_repeat_streak(agent_voices)})",
        "",
        "📈 VERTICAL DISTRIBUTION HISTOGRAM:",
    ]

    vert_counts = Counter(verticals).most_common()
    for vert, count in vert_counts[:10]:
        bar = "█" * count
        lines.append(f"  {vert:<24} | {bar:<15} ({count})")

    lines.extend([
        "",
        "🎨 LAYOUT DISTRIBUTION:",
    ])
    layout_counts = Counter(layouts).most_common()
    for lay, count in layout_counts:
        bar = "█" * count
        lines.append(f"  {lay:<24} | {bar:<15} ({count})")

    combos = [f"{lay}:{pal}" for lay, pal in zip(layouts, palettes)]
    lines.extend([
        "",
        "🛡️ COOLDOWN INTEGRITY CHECK:",
        f"  • Verticals repeat streak <= 1:     {'PASSED ✅' if max_repeat_streak(verticals) <= 1 else 'FAILED ❌'}",
        f"  • Palette repeat streak <= 1:       {'PASSED ✅' if max_repeat_streak(palettes) <= 1 else 'FAILED ❌'}",
        f"  • Layout+Palette combo streak <= 1: {'PASSED ✅' if max_repeat_streak(combos) <= 1 else 'FAILED ❌'}",
        "=" * 60,
    ])

    return "\n".join(lines)


def generate_performance_report(session: Session) -> str:
    """Generate performance and multi-armed bandit optimization summary."""
    bandit_stats = session.exec(select(BanditStat).order_by(BanditStat.alpha.desc())).all()
    metrics_records = session.exec(select(Metric)).all()

    lines = [
        "=" * 60,
        "📈 REELFORGE PERFORMANCE & LEARNING REPORT",
        "=" * 60,
        "",
        f"Total Engagement Metrics Logged: {len(metrics_records)}",
    ]

    if metrics_records:
        total_views = sum(m.views for m in metrics_records)
        total_saves = sum(m.saves for m in metrics_records)
        total_shares = sum(m.shares for m in metrics_records)
        avg_views = total_views / max(len(metrics_records), 1)
        lines.extend([
            f"  • Total Views:  {total_views:,}",
            f"  • Total Saves:  {total_saves:,}",
            f"  • Total Shares: {total_shares:,}",
            f"  • Avg Views/Reel: {avg_views:.0f}",
            "",
        ])

    lines.extend([
        "🧠 TOP-PERFORMING BANDIT ARMS (Thompson Beta Priors):",
        f"  {'Arm Key':<35} | {'Alpha':<7} | {'Beta':<7} | {'Trials':<6} | {'Expected Win':<12}",
        "-" * 75,
    ])

    if not bandit_stats:
        lines.append("  (No bandit updates yet. Arms initialize with uniform Beta(1,1) priors)")
    else:
        for b in bandit_stats[:12]:
            expected_val = b.alpha / (b.alpha + b.beta)
            lines.append(
                f"  {b.arm_key:<35} | {b.alpha:<7.2f} | {b.beta:<7.2f} | {b.n:<6d} | {expected_val:<12.1%}"
            )

    lines.append("=" * 60)
    return "\n".join(lines)
