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
    scripts.append((axes, sc))

fp = FingerprintEngine()
t1 = " ".join(t.text for t in scripts[1][1].turns)
t6 = " ".join(t.text for t in scripts[6][1].turns)
e1 = fp.get_embedding(t1)
e6 = fp.get_embedding(t6)

print("Script 1 scenario:", scripts[1][0]["scenario"])
print("Script 6 scenario:", scripts[6][0]["scenario"])
print("Script 1 text:", t1)
print("Script 6 text:", t6)
print("Cosine sim:", cosine_similarity(e1, e6))
