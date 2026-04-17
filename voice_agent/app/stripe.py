"""Create Stripe Payment Links on demand (for mid-call close).

Docs: https://stripe.com/docs/api/payment_links/payment_links/create
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class StripeError(RuntimeError):
    pass


class StripeClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.stripe.com",
        opener: Any = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._opener = opener or urllib.request.build_opener()

    def _post_form(self, path: str, form: dict) -> dict:
        import json as _json
        body = urllib.parse.urlencode(form, doseq=True).encode()
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
        try:
            with self._opener.open(req, timeout=30) as resp:
                raw = resp.read().decode()
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            raise StripeError(f"HTTP {e.code} {path}: {detail}") from e
        return _json.loads(raw) if raw else {}

    def create_payment_link(
        self,
        *,
        price_id: str,
        quantity: int = 1,
        lead_id: str,
        call_id: str | None = None,
    ) -> dict:
        """Creates a Payment Link tied to a pre-configured Price in Stripe.

        The `lead_id`/`call_id` land in metadata so when Stripe fires the
        webhook back, the CRM's stripe projector can attribute the payment
        to the right lead + call.
        """
        form = {
            "line_items[0][price]": price_id,
            "line_items[0][quantity]": str(quantity),
            "metadata[lead_id]": lead_id,
            "after_completion[type]": "hosted_confirmation",
        }
        if call_id:
            form["metadata[call_id]"] = call_id
        return self._post_form("/v1/payment_links", form)
