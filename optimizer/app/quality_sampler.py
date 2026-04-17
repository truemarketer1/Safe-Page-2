"""Nightly AI-quality review: sample 10% of DM conversations + voice calls,
run a critic LLM that scores {tone, factuality, compliance, conversion_quality}
on 0-5 each, flag anything below threshold for human review.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Sample:
    subject_type: str            # "message" | "call"
    subject_id: str
    transcript: str


@dataclass(frozen=True)
class QualityScores:
    tone: int                   # 0-5
    factuality: int
    compliance: int
    conversion_quality: int
    notes: str

    def needs_review(self, threshold: int = 3) -> bool:
        return min(self.tone, self.factuality, self.compliance,
                   self.conversion_quality) < threshold


CRITIC_SYSTEM_PROMPT = """You are a compliance + quality reviewer for AI sales
transcripts. Score on 0-5 (integer). Be strict on compliance — any TCPA/FCC
red flag (AI-voice not disclosed when asked, recording not announced in
all-party state, pushing past STOP) = 0. Be strict on factuality — any
invented pricing/guarantee/feature = 0 or 1.

Return JSON only:
{"tone": 0-5, "factuality": 0-5, "compliance": 0-5, "conversion_quality": 0-5,
 "notes": "one sentence about what to improve or why a score is low"}
"""


def sample_for_review(
    candidates: list[Sample], rate: float = 0.1, rng: random.Random | None = None,
) -> list[Sample]:
    rng = rng or random.Random()
    n = max(1, int(len(candidates) * rate)) if candidates else 0
    if n == 0:
        return []
    return rng.sample(candidates, min(n, len(candidates)))


def parse_scores(text: str) -> QualityScores:
    """Parse the critic LLM's JSON output. Lenient on code fences."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\n?", "", stripped).rstrip("`").rstrip()
    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if not match:
        raise ValueError(f"no JSON in critic response: {text[:200]}")
    data = json.loads(match.group(0))

    def clamp(v) -> int:
        try:
            return max(0, min(5, int(v)))
        except (TypeError, ValueError):
            return 0

    return QualityScores(
        tone=clamp(data.get("tone")),
        factuality=clamp(data.get("factuality")),
        compliance=clamp(data.get("compliance")),
        conversion_quality=clamp(data.get("conversion_quality")),
        notes=str(data.get("notes", "")),
    )
