"""Configuration loaded from environment variables.

Populated from process env or a `.env` file in the working directory.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv(Path.cwd() / ".env")


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required env var {name}. Set it in your shell or .env file."
        )
    return value


@dataclass(frozen=True)
class Settings:
    heygen_api_key: str
    avatar_id: str
    voice_id: str
    core_video_path: Path
    hooks_csv_path: Path
    output_dir: Path
    cache_dir: Path
    video_width: int
    video_height: int
    poll_interval_seconds: float
    poll_timeout_seconds: float
    max_parallel_generations: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            heygen_api_key=_require("HEYGEN_API_KEY"),
            avatar_id=_require("HEYGEN_AVATAR_ID"),
            voice_id=_require("HEYGEN_VOICE_ID"),
            core_video_path=Path(os.environ.get("CORE_VIDEO_PATH", "core_message.mp4")),
            hooks_csv_path=Path(os.environ.get("HOOKS_CSV_PATH", "hooks.csv")),
            output_dir=Path(os.environ.get("OUTPUT_DIR", "output")),
            cache_dir=Path(os.environ.get("CACHE_DIR", ".hook_cache")),
            video_width=int(os.environ.get("VIDEO_WIDTH", "1080")),
            video_height=int(os.environ.get("VIDEO_HEIGHT", "1920")),
            poll_interval_seconds=float(os.environ.get("POLL_INTERVAL_SECONDS", "5")),
            poll_timeout_seconds=float(os.environ.get("POLL_TIMEOUT_SECONDS", "600")),
            max_parallel_generations=int(os.environ.get("MAX_PARALLEL_GENERATIONS", "4")),
        )
