import random

import pytest

from app.hook_rerank import HookRow, pick_top_and_kill, score_hook, build_remix_prompt
from app.quality_sampler import Sample, parse_scores, sample_for_review
from app.spend_guard import ServiceMetric, evaluate


# --- hook re-rank ------------------------------------------------------------

def test_score_hook_prefers_revenue_over_plays():
    winner = HookRow("a", "rev hook", "aida", plays=10_000, completion_rate=0.2,
                     closes=5, revenue_usd=10_000)
    loser = HookRow("b", "play hook", "pas", plays=1_000_000, completion_rate=0.3,
                    closes=0, revenue_usd=0)
    assert score_hook(winner) > score_hook(loser)


def test_pick_top_and_kill_returns_balanced_slices():
    rows = [
        HookRow(str(i), f"h{i}", "aida", plays=i * 1000, completion_rate=0.1,
                closes=i, revenue_usd=i * 500)
        for i in range(1, 11)
    ]
    top, kill = pick_top_and_kill(rows, keep_ratio=0.3)
    assert len(top) == 3
    assert len(kill) == 3
    # highest revenue at top, lowest at bottom
    assert top[0].revenue_usd > top[-1].revenue_usd
    assert kill[-1].revenue_usd < top[-1].revenue_usd


def test_pick_top_and_kill_handles_empty():
    assert pick_top_and_kill([]) == ([], [])


def test_build_remix_prompt_embeds_context():
    winners = [HookRow("1", "stop scrolling", "pov", 10_000, 0.25, 3, 5000)]
    prompt = build_remix_prompt(winners, 5)
    assert "Write 5" in prompt
    assert "stop scrolling" in prompt
    assert "[pov]" in prompt


# --- quality sampler ---------------------------------------------------------

def test_sample_for_review_takes_at_least_one():
    candidates = [Sample("message", str(i), "x") for i in range(5)]
    out = sample_for_review(candidates, rate=0.1, rng=random.Random(0))
    assert len(out) >= 1


def test_sample_for_review_empty_input_returns_empty():
    assert sample_for_review([], 0.1) == []


def test_parse_scores_clamps_values():
    text = '{"tone": 99, "factuality": -3, "compliance": "bad", ' \
           '"conversion_quality": 3, "notes": "ok"}'
    s = parse_scores(text)
    assert s.tone == 5
    assert s.factuality == 0
    assert s.compliance == 0
    assert s.conversion_quality == 3


def test_parse_scores_strips_fences():
    text = '```json\n{"tone":4,"factuality":4,"compliance":4,' \
           '"conversion_quality":4,"notes":"ok"}\n```'
    s = parse_scores(text)
    assert s.tone == 4
    assert s.needs_review(threshold=3) is False


def test_quality_scores_needs_review_threshold():
    s = parse_scores('{"tone":4,"factuality":4,"compliance":2,' \
                     '"conversion_quality":4,"notes":"compliance slip"}')
    assert s.needs_review(threshold=3) is True


# --- spend guard -------------------------------------------------------------

def test_spend_guard_ok_under_cap():
    v = evaluate(ServiceMetric("retell", spend_today_usd=10, cap_usd=100))
    assert v.action == "ok"
    assert v.reasons == []


def test_spend_guard_warns_above_90_percent():
    v = evaluate(ServiceMetric("retell", spend_today_usd=91, cap_usd=100))
    assert v.action == "warn"


def test_spend_guard_pauses_at_cap():
    v = evaluate(ServiceMetric("retell", spend_today_usd=100, cap_usd=100))
    assert v.action == "pause"


def test_spend_guard_pauses_on_connect_collapse():
    v = evaluate(ServiceMetric(
        "retell", spend_today_usd=10, cap_usd=100,
        connect_rate_today=0.1, connect_rate_baseline=0.5,
    ))
    assert v.action == "pause"


def test_spend_guard_pauses_on_close_collapse():
    v = evaluate(ServiceMetric(
        "retell", spend_today_usd=10, cap_usd=100,
        close_rate_today=0.01, close_rate_baseline=0.1,
    ))
    assert v.action == "pause"
