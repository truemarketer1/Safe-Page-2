import json
from unittest.mock import MagicMock

import pytest

from reels.submagic import SubmagicClient, SubmagicError


def _resp(payload: dict):
    body = json.dumps(payload).encode()
    r = MagicMock()
    r.read.return_value = body
    r.__enter__ = lambda self: self
    r.__exit__ = lambda *a: None
    return r


def test_submit_returns_job_id():
    opener = MagicMock()
    opener.open.return_value = _resp({"data": {"id": "job-1"}})
    client = SubmagicClient(api_key="k", opener=opener)
    assert client.submit("https://cdn/x.mp4") == "job-1"


def test_submit_missing_id_raises():
    opener = MagicMock()
    opener.open.return_value = _resp({"data": {}})
    client = SubmagicClient(api_key="k", opener=opener)
    with pytest.raises(SubmagicError):
        client.submit("https://cdn/x.mp4")


def test_wait_returns_completed_job():
    opener = MagicMock()
    opener.open.side_effect = [
        _resp({"data": {"status": "processing"}}),
        _resp({"data": {"status": "completed", "output_url": "https://cdn/out.mp4"}}),
    ]
    client = SubmagicClient(api_key="k", opener=opener)
    sleeps: list[float] = []
    job = client.wait("job-1", poll_interval=1,
                      sleep_fn=sleeps.append, now_fn=lambda: 0)
    assert job.video_url == "https://cdn/out.mp4"
    assert sleeps == [1]


def test_wait_raises_on_failed():
    opener = MagicMock()
    opener.open.return_value = _resp({"data": {"status": "failed", "error": "boom"}})
    client = SubmagicClient(api_key="k", opener=opener)
    with pytest.raises(SubmagicError, match="boom"):
        client.wait("job-1", sleep_fn=lambda _: None, now_fn=lambda: 0)
