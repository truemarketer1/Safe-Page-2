"""Read hook text rows from a CSV or a Google Sheet."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Hook:
    index: int
    text: str

    @property
    def slug(self) -> str:
        safe = "".join(c if c.isalnum() else "_" for c in self.text.lower())
        return f"{self.index:03d}_{safe[:40].strip('_')}"


def read_csv_hooks(path: Path, column: str = "hook") -> list[Hook]:
    """Parse hooks from a CSV. Column header defaults to ``hook``.

    Accepts either a header row (matching ``column``) or a single-column file
    with no header.
    """
    if not path.exists():
        raise FileNotFoundError(f"hooks csv not found: {path}")
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        rows = [r for r in reader if r and any(cell.strip() for cell in r)]
    if not rows:
        return []
    header = [c.strip().lower() for c in rows[0]]
    if column in header:
        idx = header.index(column)
        body = rows[1:]
    else:
        idx = 0
        body = rows
    hooks: list[Hook] = []
    for i, row in enumerate(body, start=1):
        if idx >= len(row):
            continue
        text = row[idx].strip()
        if text:
            hooks.append(Hook(index=i, text=text))
    return hooks


def read_google_sheet_hooks(
    sheet_id: str, range_a1: str, service_account_file: str
) -> list[Hook]:
    """Read hooks from a Google Sheet using the Sheets API.

    Requires ``google-api-python-client`` and ``google-auth``. Imported lazily
    so the core pipeline can run with zero third-party deps.
    """
    try:
        from google.oauth2 import service_account  # type: ignore
        from googleapiclient.discovery import build  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "Google Sheets support requires google-api-python-client and google-auth. "
            "Install: pip install google-api-python-client google-auth"
        ) from e

    creds = service_account.Credentials.from_service_account_file(
        service_account_file,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    resp = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range=range_a1)
        .execute()
    )
    rows = resp.get("values", [])
    return [
        Hook(index=i, text=row[0].strip())
        for i, row in enumerate(rows, start=1)
        if row and row[0].strip()
    ]
