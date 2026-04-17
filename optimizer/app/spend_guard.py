"""Daily spend guardrails — kill switch for the dialer + content pipeline
if anything goes anomalous.

Checks the CRM's daily metrics; returns a structured verdict per service that
an orchestrator can use to auto-pause flows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Action = Literal["ok", "warn", "pause"]


@dataclass(frozen=True)
class ServiceMetric:
    name: str
    spend_today_usd: float
    cap_usd: float
    connect_rate_today: float | None = None   # 0..1
    connect_rate_baseline: float | None = None  # 0..1
    close_rate_today: float | None = None
    close_rate_baseline: float | None = None


@dataclass(frozen=True)
class Verdict:
    service: str
    action: Action
    reasons: list[str]


def evaluate(metric: ServiceMetric) -> Verdict:
    reasons: list[str] = []
    action: Action = "ok"

    # Hard cap.
    if metric.spend_today_usd >= metric.cap_usd:
        reasons.append(f"spend ${metric.spend_today_usd:.2f} >= cap ${metric.cap_usd:.2f}")
        action = "pause"
    elif metric.spend_today_usd >= metric.cap_usd * 0.9:
        reasons.append(f"spend {metric.spend_today_usd / metric.cap_usd:.0%} of cap")
        action = "warn" if action == "ok" else action

    # Connect rate collapse (for voice).
    if (
        metric.connect_rate_today is not None
        and metric.connect_rate_baseline is not None
        and metric.connect_rate_today < metric.connect_rate_baseline * 0.5
    ):
        reasons.append(
            f"connect rate {metric.connect_rate_today:.0%} < 50% of baseline "
            f"{metric.connect_rate_baseline:.0%}"
        )
        action = "pause"

    # Close rate collapse.
    if (
        metric.close_rate_today is not None
        and metric.close_rate_baseline is not None
        and metric.close_rate_today < metric.close_rate_baseline * 0.5
    ):
        reasons.append(
            f"close rate {metric.close_rate_today:.0%} < 50% of baseline "
            f"{metric.close_rate_baseline:.0%}"
        )
        action = "pause"

    return Verdict(service=metric.name, action=action, reasons=reasons)


def evaluate_all(metrics: list[ServiceMetric]) -> list[Verdict]:
    return [evaluate(m) for m in metrics]
