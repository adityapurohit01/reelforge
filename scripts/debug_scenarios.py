import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from reelforge.diversity.sampler import NoveltySampler
from reelforge.pipeline.stages.profile import generate_business_profile
from reelforge.pipeline.stages.dialogue import generate_dialogue
from reelforge.diversity.fingerprint import FingerprintEngine, cosine_similarity

s = NoveltySampler()
h = []
scripts = []
for i in range(10):
    axes, _ = s.sample_plan(history=h, seed=7000 + i * 43)
    h.insert(0, axes)
    prof = generate_business_profile(axes, seed=7000 + i * 43, use_llm=False)
    sc = generate_dialogue(axes, prof, seed=7000 + i * 43, use_llm=False)
    scripts.append((axes["scenario"], axes["vertical"], " ".join(t.text for t in sc.turns)))

for idx, (scen, vert, txt) in enumerate(scripts):
    print(f"[{idx}] {vert} | {scen} | {txt[:60]}...")
