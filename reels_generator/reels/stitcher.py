"""FFmpeg-based video concatenation.

Re-encodes both clips to a common codec/resolution before concatenation so the
hook (from HeyGen) and the core video (whatever you filmed) line up cleanly.
Falls back to concat demuxer stream-copy if sources already match.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class StitchError(RuntimeError):
    pass


@dataclass(frozen=True)
class StitchSpec:
    hook_path: Path
    core_path: Path
    output_path: Path
    width: int = 1080
    height: int = 1920
    fps: int = 30


def _require_ffmpeg() -> str:
    binary = shutil.which("ffmpeg")
    if not binary:
        raise StitchError(
            "ffmpeg not found on PATH. Install it: https://ffmpeg.org/download.html"
        )
    return binary


def build_ffmpeg_command(spec: StitchSpec, ffmpeg_bin: str = "ffmpeg") -> list[str]:
    """Return the ffmpeg argv for a hook+core concatenation.

    Exposed so tests can verify the command without needing ffmpeg installed.
    Uses the concat filter (re-encoding) with scale+pad+setsar to normalize
    aspect, which is safer than concat demuxer when sources differ.
    """
    target = f"scale={spec.width}:{spec.height}:force_original_aspect_ratio=decrease,"
    target += f"pad={spec.width}:{spec.height}:(ow-iw)/2:(oh-ih)/2,setsar=1"
    filter_complex = (
        f"[0:v]{target},fps={spec.fps}[v0];"
        f"[1:v]{target},fps={spec.fps}[v1];"
        "[0:a]aresample=async=1[a0];"
        "[1:a]aresample=async=1[a1];"
        "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]"
    )
    return [
        ffmpeg_bin,
        "-y",
        "-i",
        str(spec.hook_path),
        "-i",
        str(spec.core_path),
        "-filter_complex",
        filter_complex,
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(spec.output_path),
    ]


def stitch(spec: StitchSpec, runner=subprocess.run) -> Path:
    """Run ffmpeg to produce the final Reel and return the output path."""
    if not spec.hook_path.exists():
        raise StitchError(f"hook not found: {spec.hook_path}")
    if not spec.core_path.exists():
        raise StitchError(f"core video not found: {spec.core_path}")
    spec.output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_ffmpeg_command(spec, _require_ffmpeg())
    result = runner(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise StitchError(
            f"ffmpeg failed (exit {result.returncode}):\n{result.stderr[-2000:]}"
        )
    return spec.output_path
