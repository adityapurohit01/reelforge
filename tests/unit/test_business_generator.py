"""Unit & acceptance test for Phase 1: 15 business profiles with 0 collisions and 100% validity."""
from reelforge.diversity.sampler import NoveltySampler
from reelforge.pipeline.stages.profile import BusinessProfile, generate_business_profile


def test_generate_15_business_profiles_zero_collisions():
    sampler = NoveltySampler()
    history = []
    generated_names = set()
    profiles = []

    for i in range(15):
        seed = 5000 + i * 19
        axes, _ = sampler.sample_plan(history=history, seed=seed)
        history.insert(0, axes)

        # Generate business profile (synthetic/guaranteed repair mode)
        profile = generate_business_profile(axes, seed=seed, use_llm=False)
        assert isinstance(profile, BusinessProfile)
        
        # Verify schema validity
        assert len(profile.name) > 3
        assert len(profile.services) >= 6
        assert len(profile.faqs) >= 5
        assert profile.hours.weekdays
        assert profile.booking_rules.slot_length_mins > 0

        # Verify zero name collisions
        norm_name = profile.name.strip().lower()
        assert norm_name not in generated_names, f"Collision detected for business name: {profile.name}"
        generated_names.add(norm_name)
        profiles.append(profile)

    assert len(profiles) == 15
    assert len(generated_names) == 15
