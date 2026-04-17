# Optimizer

Closed-loop self-improvement jobs. Each is a pure function + CLI so any
scheduler (cron, n8n, GitHub Actions) can drive it.

## Jobs

1. **Hook auto-rerank** (`app/hook_rerank.py`): read `hook_leaderboard` view,
   find top 30% by revenue + completion rate, ask an LLM to write variations
   that preserve what made them work; mark the bottom 30% as retired.
2. **AI quality sampler** (`app/quality_sampler.py`): sample 10% of DM +
   voice transcripts nightly, run a critic LLM that scores tone / factuality
   / compliance / conversion_quality on 0-5; anything below threshold flags
   for human review in `ai_quality_reviews`.
3. **Spend guard** (`app/spend_guard.py`): compare today's spend + connect/close
   rates per service against the cap + baseline; return `ok` / `warn` / `pause`.
   Orchestrator uses the `pause` verdict as a kill switch.

## Tests

```bash
cd optimizer && pip install -e .[dev] && python -m pytest
```

14 pytest cases cover scoring, top/bottom partitioning, critic JSON parsing
with clamping, threshold flagging, hard cap + rate collapse detection.

## Wire-up

These are library functions. Driver scripts that SELECT from the CRM,
call Claude, and UPDATE hook rows will land in `optimizer/app/jobs/` next.
For now: call directly from an n8n "execute function" node.
