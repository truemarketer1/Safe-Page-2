from unittest.mock import MagicMock

import pytest

from app.llm import LLMResult
from app.qualifier import OfferConfig, _coerce_json, qualify_turn


OFFER = OfferConfig(
    brand_voice_name="Maya",
    offer_category="business coaching",
    offer_name="Scale to $30k",
    offer_price="$2,500",
    offer_promise="a clear path to $30k in 60 days",
    icp_description="coaches <$10k/mo",
    calendar_url="https://cal.com/maya/discovery",
)


def _fake_llm(response_text: str, tokens_in: int = 100, tokens_out: int = 60) -> MagicMock:
    llm = MagicMock()
    llm.messages.return_value = LLMResult(
        text=response_text, tokens_in=tokens_in, tokens_out=tokens_out, stop_reason="end_turn",
    )
    return llm


def test_qualify_parses_structured_json() -> None:
    llm = _fake_llm("""
{"reply":"what's the biggest thing blocking you right now?",
 "decision":"continue","lead_score":62,"lead_tier":"silver",
 "pain":"no consistent client flow","timeline":"now",
 "fit_signals":["active business"],"reasoning":"early signal"}
""")
    r = qualify_turn(llm=llm, offer=OFFER, history=[],
                     new_message="I saw your reel about scaling")
    assert r.decision == "continue"
    assert r.lead_score == 62
    assert r.lead_tier == "silver"
    assert r.pain == "no consistent client flow"
    assert r.timeline == "now"
    assert "blocking you" in r.reply
    assert r.tokens_in == 100


def test_qualify_coerces_bad_enums_to_safe_defaults() -> None:
    llm = _fake_llm("""
{"reply":"ok","decision":"bookNow","lead_tier":"platinum",
 "timeline":"eventually","lead_score":500,"fit_signals":[]}
""")
    r = qualify_turn(llm=llm, offer=OFFER, history=[], new_message="hi")
    assert r.decision == "continue"
    assert r.lead_tier == "bronze"
    assert r.timeline == "unknown"
    assert r.lead_score == 100  # clamped


def test_qualify_strips_code_fences() -> None:
    llm = _fake_llm("""```json
{"reply":"ok","decision":"book","lead_score":88,"lead_tier":"gold",
 "timeline":"now","fit_signals":["budget confirmed"]}
```""")
    r = qualify_turn(llm=llm, offer=OFFER, history=[],
                     new_message="yes I can invest $2500")
    assert r.decision == "book"
    assert r.lead_tier == "gold"


def test_qualify_rejects_empty_message() -> None:
    with pytest.raises(ValueError):
        qualify_turn(llm=_fake_llm("{}"), offer=OFFER, history=[], new_message="   ")


def test_coerce_json_no_object_raises() -> None:
    with pytest.raises(ValueError):
        _coerce_json("just prose, no json here")
