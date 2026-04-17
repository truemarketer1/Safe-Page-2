import datetime as dt
from pathlib import Path
from unittest.mock import MagicMock

from reels.r2 import R2Config, R2Uploader, _sign_sigv4_put


def _cfg() -> R2Config:
    return R2Config(
        account_id="acc",
        access_key_id="AKIDEXAMPLE",
        secret_access_key="wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY",
        bucket="reels",
        public_base_url="https://assets.example.com",
    )


def test_sigv4_produces_stable_signature_fields():
    now = dt.datetime(2026, 5, 1, 12, 0, 0, tzinfo=dt.UTC)
    url, headers = _sign_sigv4_put(_cfg(), "path/x.mp4", b"hello", "video/mp4", now)
    assert url.endswith("/reels/path/x.mp4")
    assert headers["x-amz-date"] == "20260501T120000Z"
    assert headers["Content-Type"] == "video/mp4"
    assert "AWS4-HMAC-SHA256" in headers["Authorization"]
    assert "Credential=AKIDEXAMPLE/20260501/auto/s3/aws4_request" in headers["Authorization"]


def test_upload_file_returns_public_url(tmp_path: Path) -> None:
    video = tmp_path / "v.mp4"
    video.write_bytes(b"fake video bytes")

    opener = MagicMock()
    resp = MagicMock()
    resp.status = 200
    resp.__enter__ = lambda self: self
    resp.__exit__ = lambda *a: None
    opener.open.return_value = resp

    fixed = dt.datetime(2026, 5, 1, 12, 0, 0, tzinfo=dt.UTC)
    uploader = R2Uploader(_cfg(), opener=opener, now_fn=lambda: fixed)
    url = uploader.upload_file(video, "reels/2026/05/01/hi.mp4")
    assert url == "https://assets.example.com/reels/2026/05/01/hi.mp4"
    # One HTTP call with PUT method.
    req = opener.open.call_args[0][0]
    assert req.method == "PUT"
    assert req.data == b"fake video bytes"
