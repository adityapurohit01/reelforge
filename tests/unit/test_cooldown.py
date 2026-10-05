"""Unit tests for diversity cooldown engine and relaxation order."""
import pytest
from reelforge.config import CooldownsConfig
from reelforge.diversity.cooldown import CooldownEngine


def test_consecutive_vertical_forbidden():
    engine = CooldownEngine(CooldownsConfig(vertical=5))
    history = [{"vertical": "hair_salon", "city": "Pune", "scenario": "new_booking", "hook_style": "pov_hands_full"}]
    candidate = {"vertical": "hair_salon", "city": "Mumbai", "scenario": "reschedule", "hook_style": "question_hook"}
    
    violations = engine.check_candidate(candidate, history)
    assert any(v.rule_name == "consecutive_vertical_forbidden" for v in violations)


def test_vertical_cooldown_within_5():
    engine = CooldownEngine(CooldownsConfig(vertical=5))
    history = [
        {"vertical": "auto_repair"},
        {"vertical": "plumbing"},
        {"vertical": "bakery"},
        {"vertical": "dental"},
        {"vertical": "hair_salon"},  # 5th item
    ]
    # hair_salon is at distance 5 -> should trigger cooldown violation
    candidate = {"vertical": "hair_salon"}
    violations = engine.check_candidate(candidate, history)
    assert any(v.axis == "vertical" for v in violations)

    # 6th item (outside cooldown window 5)
    history_extended = [{"vertical": "x"} for _ in range(5)] + [{"vertical": "hair_salon"}]
    violations_outside = engine.check_candidate(candidate, history_extended)
    assert not any(v.axis == "vertical" for v in violations_outside)


def test_city_cooldown_within_6():
    engine = CooldownEngine(CooldownsConfig(city=6))
    history = [{"city": "Pune"}] + [{"city": f"City_{i}"} for i in range(4)]
    candidate = {"city": "Pune"}
    violations = engine.check_candidate(candidate, history)
    assert any(v.axis == "city" for v in violations)


def test_scenario_cooldown_within_4():
    engine = CooldownEngine(CooldownsConfig(scenario=4))
    history = [{"scenario": "reschedule"}] + [{"scenario": f"scen_{i}"} for i in range(2)]
    candidate = {"scenario": "reschedule"}
    violations = engine.check_candidate(candidate, history)
    assert any(v.axis == "scenario" for v in violations)


def test_hook_style_cooldown_within_8():
    engine = CooldownEngine(CooldownsConfig(hook_style=8))
    history = [{"hook_style": "pov_hands_full"}] + [{"hook_style": f"hook_{i}"} for i in range(6)]
    candidate = {"hook_style": "pov_hands_full"}
    violations = engine.check_candidate(candidate, history)
    assert any(v.axis == "hook_style" for v in violations)


def test_layout_palette_combo_cooldown():
    engine = CooldownEngine(CooldownsConfig(layout_palette=6, palette_alone=1))
    history = [{"layout": "ReelA-Split", "palette": "midnight_indigo"}]
    candidate = {"layout": "ReelA-Split", "palette": "midnight_indigo"}
    violations = engine.check_candidate(candidate, history)
    assert any(v.axis == "layout_palette" for v in violations)


def test_agent_voice_max_in_5():
    engine = CooldownEngine(CooldownsConfig(agent_voice_max_in_5=2))
    history = [
        {"agent_voice": "af_bella"},
        {"agent_voice": "am_adam"},
        {"agent_voice": "af_bella"},  # af_bella appears 2 times in recent 5
        {"agent_voice": "am_michael"},
    ]
    candidate = {"agent_voice": "af_bella"}
    violations = engine.check_candidate(candidate, history)
    assert any(v.rule_name == "agent_voice_frequency_limit" for v in violations)


def test_relaxation_sequence_order():
    engine = CooldownEngine()
    ladder = engine.get_relaxation_sequence()
    keys = [item[0] for item in ladder]
    # Priority order: palette_alone -> voice_pair -> layout_palette -> hook_style -> city -> scenario -> vertical
    assert keys == [
        "palette_alone",
        "voice_pair",
        "layout_palette",
        "hook_style",
        "city",
        "scenario",
        "vertical",
    ]
