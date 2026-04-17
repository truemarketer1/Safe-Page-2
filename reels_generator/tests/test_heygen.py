import io
import json
from unittest.mock import MagicMock

import pytest

from reels.heygen import HeyGenClient, HeyGenError


def _fake_response(payload: dict | bytes, status: int = 200):
    """Build a context-manager-style fake urllib response."""
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__ = lambda self: self
    resp.__exit__ = lambda *a: None
    return resp


def _client_with_opener(responses):
    opener = MagicMock()
    opener.open.side_effect = responses
    return HeyGenClient(
        api_key="k",
        avatar_id="av",
        voice_id="vo",
        opener=opener,
    ), opener


def test_submit_hook_extracts_video_id():
    client, opener = _client_with_opener(
        [_fake_response({"data": {"video_id": "vid-123"}})]
    )
    assert client.submit_hook("hello world") == "vid-123"
    req = opener.open.call_args[0][0]
    assert req.full_url.endswith("/v2/video/generate")
    assert req.get_header("X-api-key") == "k"
    body = json.loads(req.data)
    assert body["video_inputs"][0]["voice"]["input_text"] == "hello world"
    assert body["video_inputs"][0]["character"]["avatar_id"] == "av"


def test_submit_hook_rejects_empty_text():
    client, _ = _client_with_opener([])
    with pytest.raises(ValueError):
        client.submit_hook("   ")


def test_submit_hook_missing_video_id_raises():
    client, _ = _client_with_opener([_fake_response({"data": {}})])
    with pytest.raises(HeyGenError, match="No video_id"):
        client.submit_hook("hi")


def test_wait_for_completion_returns_on_completed():
    client, _ = _client_with_opener(
        [
            _fake_response({"data": {"status": "processing"}}),
            _fake_response(
                {"data": {"status": "completed", "video_url": "http://cdn/x.mp4"}}
            ),
        ]
    )
    sleeps: list[float] = []
    job = client.wait_for_completion(
        "vid-1",
        poll_interval=1,
        timeout=60,
        sleep_fn=sleeps.append,
        now_fn=lambda: 0,
    )
    assert job.status == "completed"
    assert job.video_url == "http://cdn/x.mp4"
    assert sleeps == [1]


def test_wait_for_completion_raises_on_failed():
    client, _ = _client_with_opener(
        [_fake_response({"data": {"status": "failed", "error": "oops"}})]
    )
    with pytest.raises(HeyGenError, match="oops"):
        client.wait_for_completion("vid-1", sleep_fn=lambda _: None, now_fn=lambda: 0)


def test_wait_for_completion_times_out():
    responses = [_fake_response({"data": {"status": "processing"}})] * 5
    client, _ = _client_with_opener(responses)
    times = iter([0, 0, 10, 20, 100])
    with pytest.raises(HeyGenError, match="Timed out"):
        client.wait_for_completion(
            "vid-1",
            poll_interval=1,
            timeout=30,
            sleep_fn=lambda _: None,
            now_fn=lambda: next(times),
        )


def test_download_writes_full_payload(tmp_path):
    chunks = [b"abc", b"def", b""]

    class FakeResp(io.IOBase):
        def __enter__(self_):
            return self_

        def __exit__(self_, *a):
            return False

        def read(self_, n):
            return chunks.pop(0)

    opener = MagicMock()
    opener.open.return_value = FakeResp()
    client = HeyGenClient("k", "a", "v", opener=opener)
    dest = tmp_path / "out.mp4"
    client.download("http://cdn/x.mp4", dest)
    assert dest.read_bytes() == b"abcdef"
