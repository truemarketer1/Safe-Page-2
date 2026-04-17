"""Webhook signature verification — one function per provider.

Each webhook provider signs with a different scheme. Implementing a verifier per
source means a leaked secret only blasts its own surface, not the whole API.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Callable


def _safe_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def verify_stripe(secret: str, signature_header: str, payload: bytes, tolerance: int = 300) -> bool:
    """Stripe signs as `t=<ts>,v1=<hex>`. Re-sign `<ts>.<payload>` and compare."""
    if not secret or not signature_header:
        return False
    parts = {k: v for k, v in (p.split("=", 1) for p in signature_header.split(",") if "=" in p)}
    ts = parts.get("t")
    sig = parts.get("v1")
    if not ts or not sig:
        return False
    try:
        if abs(time.time() - int(ts)) > tolerance:
            return False
    except ValueError:
        return False
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return _safe_eq(mac, sig)


def verify_meta(secret: str, signature_header: str, payload: bytes) -> bool:
    """Meta signs as `sha256=<hex>` over the raw body."""
    if not secret or not signature_header:
        return False
    if not signature_header.startswith("sha256="):
        return False
    expected = signature_header.split("=", 1)[1]
    mac = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return _safe_eq(mac, expected)


def verify_shared_secret(secret: str, header_value: str) -> bool:
    """Generic shared-secret comparison (Cal.com, ManyChat, Retell custom)."""
    if not secret or not header_value:
        return False
    return _safe_eq(header_value, secret)


VERIFIERS: dict[str, Callable[..., bool]] = {
    "stripe": verify_stripe,
    "meta": verify_meta,
    "cal": verify_shared_secret,
    "retell": verify_shared_secret,
    "manychat": verify_shared_secret,
}
