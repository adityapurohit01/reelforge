"""Layer 3 Semantic de-duplication gate and fingerprint storage."""
import json
import pickle
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import httpx
import numpy as np
from sqlmodel import Session, select

from reelforge.config import ReelForgeConfig, load_config
from reelforge.models import Fingerprint


def extract_words(text: str) -> List[str]:
    """Clean and tokenize text into words."""
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return [w for w in cleaned.split() if w]


def extract_trigrams(text: str) -> Set[Tuple[str, str, str]]:
    """Extract word 3-grams from text."""
    words = extract_words(text)
    if len(words) < 3:
        return set()
    return {tuple(words[i : i + 3]) for i in range(len(words) - 2)}


def jaccard_similarity(set_a: Set[Any], set_b: Set[Any]) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    return float(intersection / union) if union > 0 else 0.0


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """Compute cosine similarity between two 1D float vectors."""
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))


class FingerprintEngine:
    def __init__(self, config: Optional[ReelForgeConfig] = None):
        self.config = config or load_config()

    def get_embedding(self, text: str) -> np.ndarray:
        """Fetch dense embedding vector from Ollama nomic-embed-text."""
        host = self.config.settings.ollama_host
        model = self.config.models.embedding_model
        models_to_try = [model, f"{model}:latest"] if ":" not in model else [model]
        
        for m in models_to_try:
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(
                        f"{host}/api/embeddings",
                        json={"model": m, "prompt": text},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        vec = np.array(data["embedding"], dtype=np.float32)
                        return vec
            except Exception as e:
                logger.debug(f"Ollama embedding attempt failed for {m}: {e}")

        # Deterministic TF-IDF / term-frequency vectorizer fallback
        words = extract_words(text)
        dim = 768
        vec = np.zeros(dim, dtype=np.float32)
        import zlib
        for w in words:
            idx = zlib.crc32(w.encode("utf-8")) % dim
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def check_duplication(
        self,
        session: Session,
        script_text: str,
        hook_text: str,
    ) -> Tuple[bool, Optional[str]]:
        """Check cosine similarity and 3-gram Jaccard against the last 50 stored fingerprints.
        Returns (is_duplicate, reason).
        """
        history_limit = self.config.similarity_thresholds.history_window
        statement = select(Fingerprint).order_by(Fingerprint.created_at.desc()).limit(history_limit)  # type: ignore
        past_fingerprints = session.exec(statement).all()

        if not past_fingerprints:
            return False, None

        current_script_emb = self.get_embedding(script_text)
        current_hook_emb = self.get_embedding(hook_text)
        current_trigrams = extract_trigrams(script_text)

        script_max = self.config.similarity_thresholds.script_cosine_max
        hook_max = self.config.similarity_thresholds.hook_cosine_max
        jaccard_max = self.config.similarity_thresholds.trigram_jaccard_max

        for fp in past_fingerprints:
            # 1. Script cosine check
            if fp.script_embedding:
                past_script_emb = np.frombuffer(fp.script_embedding, dtype=np.float32)
                sim = cosine_similarity(current_script_emb, past_script_emb)
                if sim >= script_max:
                    return True, f"Script cosine similarity {sim:.3f} >= threshold {script_max} with past fingerprint #{fp.id}"

            # 2. Hook cosine check
            if fp.hook_embedding:
                past_hook_emb = np.frombuffer(fp.hook_embedding, dtype=np.float32)
                h_sim = cosine_similarity(current_hook_emb, past_hook_emb)
                if h_sim >= hook_max:
                    return True, f"Hook cosine similarity {h_sim:.3f} >= threshold {hook_max} with past fingerprint #{fp.id}"

            # 3. Trigram Jaccard check
            if fp.trigram_set:
                past_trigrams = pickle.loads(fp.trigram_set)
                j_sim = jaccard_similarity(current_trigrams, past_trigrams)
                if j_sim >= jaccard_max:
                    return True, f"3-gram Jaccard overlap {j_sim:.3f} >= threshold {jaccard_max} with past fingerprint #{fp.id}"

        return False, None

    def store_fingerprint(
        self,
        session: Session,
        script_text: str,
        hook_text: str,
        axis_tuple: Dict[str, Any],
    ) -> Fingerprint:
        """Compute and persist fingerprint in SQLite."""
        script_emb = self.get_embedding(script_text).tobytes()
        hook_emb = self.get_embedding(hook_text).tobytes()
        trigrams = pickle.dumps(extract_trigrams(script_text))

        fp = Fingerprint(
            script_embedding=script_emb,
            hook_embedding=hook_emb,
            trigram_set=trigrams,
            axis_tuple_json=json.dumps(axis_tuple),
        )
        session.add(fp)
        session.commit()
        session.refresh(fp)
        return fp
