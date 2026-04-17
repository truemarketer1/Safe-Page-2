"""Send an SMS via Twilio — used by Retell's tool-call to drop a Stripe
Payment Link on the prospect's phone mid-call."""

from __future__ import annotations

import base64
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class TwilioError(RuntimeError):
    pass


class TwilioClient:
    def __init__(
        self,
        *,
        account_sid: str,
        auth_token: str,
        from_number: str,
        base_url: str = "https://api.twilio.com",
        opener: Any = None,
    ) -> None:
        if not account_sid or not auth_token:
            raise ValueError("account_sid and auth_token required")
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.base_url = base_url.rstrip("/")
        self._opener = opener or urllib.request.build_opener()

    def send_sms(self, to_number: str, body: str) -> dict:
        import json as _json
        url = f"{self.base_url}/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        data = urllib.parse.urlencode({
            "From": self.from_number, "To": to_number, "Body": body,
        }).encode()
        token = base64.b64encode(f"{self.account_sid}:{self.auth_token}".encode()).decode()
        req = urllib.request.Request(url, data=data, method="POST", headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        })
        try:
            with self._opener.open(req, timeout=20) as resp:
                raw = resp.read().decode()
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            raise TwilioError(f"HTTP {e.code}: {detail}") from e
        return _json.loads(raw) if raw else {}
