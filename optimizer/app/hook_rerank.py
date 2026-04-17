"""Hook leaderboard -> new hook batch.

Reads the CRM's `hook_leaderboard` view, identifies the top performers by
revenue per play, and asks an LLM to generate N variations that preserve the
winning structure but remix the angle.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HookRow:
    id: str
    hook_text: str
    hook_framework: str | None
    plays: int
    completion_rate: float | None
    closes: int
    revenue_usd: float


def score_hook(row: HookRow) -> float:
    """Composite score for sorting. Revenue dominates; completion_rate as
    tiebreaker for hooks too new to have revenue."""
    revenue_weight = row.revenue_usd
    completion_weight = (row.completion_rate or 0) * 10
    plays_weight = min(row.plays / 10_000, 5.0) if row.plays else 0
    return revenue_weight + completion_weight + plays_weight


def pick_top_and_kill(rows: list[HookRow], keep_ratio: float = 0.3
                     ) -> tuple[list[HookRow], list[HookRow]]:
    """Returns (top_keep, bottom_kill). Each has `keep_ratio` of the list."""
    if not rows:
        return [], []
    ranked = sorted(rows, key=score_hook, reverse=True)
    keep_n = max(1, int(len(ranked) * keep_ratio))
    kill_n = max(1, int(len(ranked) * keep_ratio))
    return ranked[:keep_n], ranked[-kill_n:]


REMIX_SYSTEM_PROMPT = """You are a top-1% short-form scriptwriter for Instagram
Reels. I'll give you N "winning hooks" that drove measurable revenue. Your
job: write M variations that preserve what made them work (framework,
specificity, tension) while remixing the angle so each feels fresh.

Constraints:
  - Each hook ≤ 7 seconds spoken (~18 words max).
  - Label each with the framework it uses.
  - Return strict JSON: {"hooks": [{"text": "...", "framework": "..."}]}.
"""


def build_remix_prompt(winners: list[HookRow], n_variations: int) -> str:
    lines = [f'Write {n_variations} new hooks inspired by these winners:']
    for w in winners:
        lines.append(
            f"- [{w.hook_framework or 'unknown'}] "
            f"${w.revenue_usd:.0f} / {w.closes} closes / {w.plays} plays: "
            f'"{w.hook_text}"'
        )
    return "\n".join(lines)
