from pathlib import Path
from unittest.mock import MagicMock

import pytest

from reels.stitcher import StitchError, StitchSpec, build_ffmpeg_command, stitch


def _spec(tmp_path: Path) -> StitchSpec:
    hook = tmp_path / "hook.mp4"
    core = tmp_path / "core.mp4"
    hook.write_bytes(b"fake")
    core.write_bytes(b"fake")
    return StitchSpec(
        hook_path=hook,
        core_path=core,
        output_path=tmp_path / "out" / "final.mp4",
    )


def test_build_ffmpeg_command_has_expected_structure(tmp_path: Path) -> None:
    cmd = build_ffmpeg_command(_spec(tmp_path), ffmpeg_bin="/usr/bin/ffmpeg")
    assert cmd[0] == "/usr/bin/ffmpeg"
    assert "-filter_complex" in cmd
    filter_expr = cmd[cmd.index("-filter_complex") + 1]
    assert "concat=n=2:v=1:a=1" in filter_expr
    assert "scale=1080:1920" in filter_expr
    assert cmd[-1].endswith("final.mp4")


def test_stitch_raises_when_inputs_missing(tmp_path: Path) -> None:
    spec = StitchSpec(
        hook_path=tmp_path / "missing_hook.mp4",
        core_path=tmp_path / "missing_core.mp4",
        output_path=tmp_path / "out.mp4",
    )
    with pytest.raises(StitchError, match="hook not found"):
        stitch(spec, runner=MagicMock())


def test_stitch_raises_on_ffmpeg_failure(tmp_path: Path, monkeypatch) -> None:
    spec = _spec(tmp_path)
    monkeypatch.setattr("reels.stitcher._require_ffmpeg", lambda: "/usr/bin/ffmpeg")
    runner = MagicMock(return_value=MagicMock(returncode=1, stderr="boom"))
    with pytest.raises(StitchError, match="boom"):
        stitch(spec, runner=runner)


def test_stitch_creates_output_dir_and_returns_path(
    tmp_path: Path, monkeypatch
) -> None:
    spec = _spec(tmp_path)
    monkeypatch.setattr("reels.stitcher._require_ffmpeg", lambda: "/usr/bin/ffmpeg")
    runner = MagicMock(return_value=MagicMock(returncode=0, stderr=""))
    result = stitch(spec, runner=runner)
    assert result == spec.output_path
    assert spec.output_path.parent.exists()
    runner.assert_called_once()
