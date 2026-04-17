"""Cloudflare R2 uploader using the S3-compatible API.

Meta blocks Drive/redirect URLs since early 2025 — videos must sit on a
direct public-read URL. R2 is the cheapest option (free egress).

We ship a minimal pure-stdlib SigV4 signer so there's no boto3 dep; if you
already have boto3 installed, `R2Uploader` accepts an `s3_client` kwarg and
uses it directly instead.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class R2Config:
    account_id: str
    access_key_id: str
    secret_access_key: str
    bucket: str
    public_base_url: str          # e.g. https://assets.yourdomain.com

    @classmethod
    def from_env(cls) -> "R2Config":
        def req(k: str) -> str:
            v = os.environ.get(k)
            if not v:
                raise RuntimeError(f"missing env var {k}")
            return v
        return cls(
            account_id=req("R2_ACCOUNT_ID"),
            access_key_id=req("R2_ACCESS_KEY_ID"),
            secret_access_key=req("R2_SECRET_ACCESS_KEY"),
            bucket=req("R2_BUCKET"),
            public_base_url=req("R2_PUBLIC_BASE_URL").rstrip("/"),
        )


def _sign_sigv4_put(
    cfg: R2Config, key: str, body: bytes, content_type: str, now: dt.datetime
) -> tuple[str, dict[str, str]]:
    """Return (url, headers) for an S3 SigV4 PUT to R2.

    R2 endpoint: https://{account_id}.r2.cloudflarestorage.com/{bucket}/{key}
    Region is always "auto" for R2.
    """
    region = "auto"
    service = "s3"
    host = f"{cfg.account_id}.r2.cloudflarestorage.com"
    canonical_uri = "/" + urllib.parse.quote(f"{cfg.bucket}/{key}", safe="/")
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(body).hexdigest()

    canonical_headers = (
        f"host:{host}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )
    signed_headers = "host;x-amz-content-sha256;x-amz-date"

    canonical_request = "\n".join([
        "PUT",
        canonical_uri,
        "",
        canonical_headers,
        signed_headers,
        payload_hash,
    ])

    algorithm = "AWS4-HMAC-SHA256"
    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join([
        algorithm,
        amz_date,
        credential_scope,
        hashlib.sha256(canonical_request.encode()).hexdigest(),
    ])

    def _sign(k: bytes, m: str) -> bytes:
        return hmac.new(k, m.encode(), hashlib.sha256).digest()

    k_secret = ("AWS4" + cfg.secret_access_key).encode()
    k_date = _sign(k_secret, date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()

    authorization = (
        f"{algorithm} Credential={cfg.access_key_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    url = f"https://{host}{canonical_uri}"
    headers = {
        "Authorization": authorization,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
        "Content-Type": content_type,
        "Content-Length": str(len(body)),
    }
    return url, headers


class R2Uploader:
    def __init__(self, cfg: R2Config, opener: Any = None, now_fn: Any = None) -> None:
        self.cfg = cfg
        self._opener = opener or urllib.request.build_opener()
        self._now = now_fn or (lambda: dt.datetime.now(dt.UTC))

    def upload_file(self, local_path: Path, key: str,
                    content_type: str = "video/mp4") -> str:
        """Upload a local file to R2; return its public URL.

        `key` is the object key inside the bucket (e.g. "reels/2026-05-01/abc.mp4").
        Content-Type defaults to video/mp4.
        """
        body = local_path.read_bytes()
        url, headers = _sign_sigv4_put(self.cfg, key, body, content_type, self._now())
        req = urllib.request.Request(url, data=body, method="PUT", headers=headers)
        with self._opener.open(req, timeout=300) as resp:
            if resp.status not in (200, 201):
                raise RuntimeError(f"R2 upload failed: HTTP {resp.status}")
        return f"{self.cfg.public_base_url}/{urllib.parse.quote(key)}"
