import io
import json
from unittest.mock import MagicMock

import pytest

from reels.instagram import InstagramClient, InstagramError


def _resp(payload: dict):
    body = json.dumps(payload).encode()
    r = MagicMock()
    r.read.return_value = body
    r.__enter__ = lambda self: self
    r.__exit__ = lambda *a: None
    return r


def _client(responses):
    opener = MagicMock()
    opener.open.side_effect = responses
    return InstagramClient(access_token="tok", ig_user_id="igu", opener=opener), opener


def test_create_reel_container_sends_expected_params():
    client, opener = _client([_resp({"id": "cont-1"})])
    cid = client.create_reel_container(
        video_url="https://cdn/x.mp4",
        caption="Comment SCALE for the guide.",
    )
    assert cid == "cont-1"
    req = opener.open.call_args[0][0]
    assert "media_type=REELS" in req.full_url
    assert "Comment+SCALE" in req.full_url or "Comment%20SCALE" in req.full_url
    assert req.method == "POST"


def test_wait_for_container_completes():
    responses = [
        _resp({"status_code": "IN_PROGRESS"}),
        _resp({"status_code": "FINISHED"}),
    ]
    client, _ = _client(responses)
    sleeps: list[float] = []
    client.wait_for_container("cont-1", poll_interval=1,
                              sleep_fn=sleeps.append, now_fn=lambda: 0)
    assert sleeps == [1]


def test_wait_for_container_errors_on_error_status():
    client, _ = _client([_resp({"status_code": "ERROR"})])
    with pytest.raises(InstagramError):
        client.wait_for_container("cont-1", sleep_fn=lambda _: None, now_fn=lambda: 0)


def test_publish_returns_media_id():
    client, _ = _client([_resp({"id": "ig-777"})])
    assert client.publish("cont-1") == "ig-777"


def test_post_reel_full_flow():
    client, _ = _client([
        _resp({"id": "cont-1"}),                      # create container
        _resp({"status_code": "FINISHED"}),           # status check
        _resp({"id": "ig-42"}),                       # publish
        _resp({"permalink": "https://instagram.com/reel/42"}),  # permalink
    ])
    result = client.post_reel(video_url="https://cdn/x.mp4", caption="hi")
    assert result.ig_media_id == "ig-42"
    assert result.permalink == "https://instagram.com/reel/42"
