"""Claims and compliance linter for ReelForge.
Enforces brand safety:
1. No invented statistics (e.g. '80% of calls', '99%').
2. No absolute guarantees ('never miss', '100% guaranteed', 'promise').
3. No medical, legal, or financial advice (administrative clinic/law only).
4. No competitor or real-world brand names.
5. No real phone numbers.
"""
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import yaml

PROHIBITED_GUARANTEES = [
    r"\bnever miss\b",
    r"\b100%\b",
    r"\bguarantee\b",
    r"\bguaranteed\b",
    r"\bzero errors\b",
    r"\bwe promise\b",
    r"\bflawless\b",
]

PROHIBITED_STATS = [
    r"\b\d{1,3}%\s+of\s+calls\b",
    r"\b\d{1,3}%\s+increase\b",
    r"\b\d{1,3}%\s+missed\b",
    r"\b\d+\s+out\s+of\s+\d+\b",
]

PROHIBITED_ADVICE = [
    r"\bmedical advice\b",
    r"\bprescribe\b",
    r"\bdiagnosis\b",
    r"\btreatment plan\b",
    r"\bmedication\b",
    r"\bdosage\b",
    r"\b\d+\s*mg\b",
    r"\bamoxicillin\b",
    r"\bantibiotics\b",
    r"\blegal advice\b",
    r"\blegal counsel\b",
    r"\bguaranteed win\b",
    r"\binvestment advice\b",
    r"\bfinancial return\b",
]

COMPETITOR_BRANDS = [
    r"\bbland\s*ai\b",
    r"\bretell\s*ai\b",
    r"\bvapi\b",
    r"\bsynthflow\b",
    r"\bsiri\b",
    r"\balexa\b",
]

REAL_PHONE_PATTERN = r"\b(?:\+?1[-. ]?)?\(?([0-9]{3})\)?[-. ]?([0-9]{3})[-. ]?([0-9]{4})\b"


class ClaimsLinter:
    def __init__(self, approved_claims_path: Optional[Path] = None):
        self.approved_claims = []
        path = approved_claims_path or Path("claims.yaml")
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if data and "approved_claims" in data:
                        self.approved_claims = data["approved_claims"]
            except Exception:
                pass

    def lint_text(self, text: str) -> Tuple[bool, List[str]]:
        """Lint text against brand safety and compliance rules.
        Returns (passed, list_of_violations).
        """
        violations = []
        lower_text = text.lower()

        # Check guarantees
        for pat in PROHIBITED_GUARANTEES:
            if re.search(pat, lower_text):
                violations.append(f"Prohibited guarantee phrase matching '{pat}' found in text.")

        # Check invented stats
        for pat in PROHIBITED_STATS:
            if re.search(pat, lower_text):
                violations.append(f"Invented statistics matching '{pat}' found in text.")

        # Check advice claims
        for pat in PROHIBITED_ADVICE:
            if re.search(pat, lower_text):
                violations.append(f"Prohibited medical/legal/financial advice matching '{pat}' found in text.")

        # Check competitor brands
        for pat in COMPETITOR_BRANDS:
            if re.search(pat, lower_text):
                violations.append(f"Competitor/third-party brand name matching '{pat}' found in text.")

        # Check phone numbers (allow obvious 555 fictional numbers)
        for match in re.finditer(REAL_PHONE_PATTERN, text):
            area, exch, num = match.groups()
            if exch != "555" and not text.startswith("000"):
                violations.append(f"Plausible non-fictional phone number '{match.group(0)}' detected.")

        return len(violations) == 0, violations
