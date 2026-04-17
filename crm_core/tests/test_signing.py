import hashlib
import hmac
import time

from app.signing import verify_meta, verify_shared_secret, verify_stripe


def test_verify_stripe_accepts_valid_signature() -> None:
    secret = "whsec_test"
    body = b'{"id":"evt_1"}'
    ts = str(int(time.time()))
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    header = f"t={ts},v1={sig}"
    assert verify_stripe(secret, header, body) is True


def test_verify_stripe_rejects_tampered_body() -> None:
    secret = "whsec_test"
    body = b'{"id":"evt_1"}'
    ts = str(int(time.time()))
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    header = f"t={ts},v1={sig}"
    assert verify_stripe(secret, header, b'{"id":"evt_2"}') is False


def test_verify_stripe_rejects_old_timestamp() -> None:
    secret = "whsec_test"
    body = b'{}'
    ts = str(int(time.time()) - 10_000)
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    header = f"t={ts},v1={sig}"
    assert verify_stripe(secret, header, body, tolerance=300) is False


def test_verify_stripe_rejects_empty_secret() -> None:
    assert verify_stripe("", "t=1,v1=abc", b"{}") is False


def test_verify_meta_validates_sha256_header() -> None:
    secret = "app_secret"
    body = b'{"entry":[]}'
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_meta(secret, f"sha256={sig}", body) is True
    assert verify_meta(secret, f"sha256={'0' * 64}", body) is False
    assert verify_meta(secret, sig, body) is False  # missing prefix


def test_verify_shared_secret() -> None:
    assert verify_shared_secret("abc", "abc") is True
    assert verify_shared_secret("abc", "xyz") is False
    assert verify_shared_secret("", "abc") is False
