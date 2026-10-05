"""Stage 9 Caption and Hashtag Writer for ReelForge.
Generates engaging, compliant Instagram captions, alt-text, and varied hashtags.
"""
import logging
import random
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from reelforge.config import ReelForgeConfig, load_config
from reelforge.pipeline.stages.dialogue import DialogueScript
from reelforge.pipeline.stages.profile import BusinessProfile
from reelforge.qc.claims_lint import ClaimsLinter

logger = logging.getLogger(__name__)


class InstagramPostMetadata(BaseModel):
    caption: str
    alt_text: str
    hashtags: List[str]
    hook_line: str
    disclosure: str


def generate_post_caption(
    profile: BusinessProfile,
    script: DialogueScript,
    plan_axes: Dict[str, Any],
    seed: int = 42,
    config: Optional[ReelForgeConfig] = None,
) -> InstagramPostMetadata:
    """Generate high-performing, compliant Instagram Reel caption and metadata."""
    cfg = config or load_config()
    rng = random.Random(seed)
    linter = ClaimsLinter()

    vertical = profile.vertical
    city = profile.city
    biz_name = profile.name
    service = script.turns[1].text if len(script.turns) > 1 else "client services"

    # Distinct caption hook templates that differ from on-video hook
    hook_templates = [
        f"Ever wonder how {biz_name} handles client calls without picking up the phone?",
        f"This is how small business reception is changing in {city}.",
        f"Zero hold times, zero missed appointments. See AI front desk in action.",
        f"When {biz_name} gets busy, their AI receptionist takes the wheel.",
        f"A real look at automated phone booking for {vertical.lower()}s.",
    ]
    caption_hook = rng.choice(hook_templates)

    # Body lines
    body_lines = [
        f"Our AI answers live inquiries, checks real-time slot availability, and logs appointments directly on the calendar.",
        f"From after-hours emergencies to routine bookings, every caller receives instant, personalized attention.",
        f"Owners get immediate WhatsApp & Telegram alerts with complete caller summaries.",
    ]

    cta_lines = [
        f"Want an AI receptionist for your business? Link in bio to learn more ({cfg.product.cta_url}).",
        f"Automate your front desk with {cfg.product.name}. Visit {cfg.product.cta_url} to try a demo.",
        f"Stop losing leads to voicemail. Discover {cfg.product.name} at {cfg.product.cta_url}.",
    ]
    cta = rng.choice(cta_lines)

    disclosure = "Simulated phone call for demonstration purposes. Fictional business profile."

    # Dynamic varied hashtags (vertical, local, industry, product)
    clean_vert = re_tag(vertical)
    clean_city = re_tag(city)
    
    vertical_tags = [f"#{clean_vert}", f"#{clean_vert}Business", f"#{clean_vert}Owners"]
    local_tags = [f"#{clean_city}", f"#{clean_city}Business", f"#{clean_city}SmallBiz"]
    tech_tags = ["#AIReceptionist", "#VoiceAI", "#SmallBusinessAutomation", "#AIAutomation"]

    chosen_tags = [
        rng.choice(vertical_tags),
        rng.choice(local_tags),
        rng.choice(tech_tags),
        "#VocalisAI",
    ]
    # Remove any duplicates while preserving order
    unique_tags = list(dict.fromkeys(chosen_tags))

    caption = (
        f"{caption_hook}\n\n"
        f"{' '.join(body_lines[:2])}\n\n"
        f"{cta}\n\n"
        f"ℹ️ {disclosure}\n\n"
        f"{' '.join(unique_tags)}"
    )

    alt_text = (
        f"Video demonstration showing an AI voice receptionist answering an inbound call for fictional business "
        f"{biz_name} in {city}, booking a service appointment and sending automated notifications."
    )

    # Claims lint check
    passed, violations = linter.lint_text(caption)
    if not passed:
        logger.warning(f"Caption generated with claims warning: {violations}")

    return InstagramPostMetadata(
        caption=caption,
        alt_text=alt_text,
        hashtags=unique_tags,
        hook_line=caption_hook,
        disclosure=disclosure,
    )


def re_tag(s: str) -> str:
    """Helper to convert phrase to CamelCase hashtag."""
    return "".join(w.capitalize() for w in s.replace("-", " ").replace("_", " ").split())
