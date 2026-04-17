from pathlib import Path
from unittest.mock import MagicMock

from reels.config import Settings
from reels.heygen import VideoJob
from reels.hooks_source import Hook
from reels.pipeline import generate_hook_video, run_pipeline


def _settings(tmp_path: Path, **overrides) -> Settings:
    defaults = dict(
        heygen_api_key="k",
        avatar_id="av",
        voice_id="vo",
        core_video_path=tmp_path / "core.mp4",
        hooks_csv_path=tmp_path / "hooks.csv",
        output_dir=tmp_path / "out",
        cache_dir=tmp_path / "cache",
        video_width=1080,
        video_height=1920,
        poll_interval_seconds=0,
        poll_timeout_seconds=1,
        max_parallel_generations=2,
    )
    defaults.update(overrides)
    return Settings(**defaults)


def test_generate_hook_video_uses_cache(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    hook = Hook(index=1, text="hey")
    client = MagicMock()

    def fake_submit(_text):
        return "vid-1"

    def fake_wait(_id, **_):
        return VideoJob(video_id="vid-1", status="completed", video_url="http://x")

    def fake_download(_url, dest):
        Path(dest).write_bytes(b"video-data")

    client.submit_hook.side_effect = fake_submit
    client.wait_for_completion.side_effect = fake_wait
    client.download.side_effect = fake_download

    path1 = generate_hook_video(client, settings, hook)
    assert path1.exists()
    assert client.submit_hook.call_count == 1

    path2 = generate_hook_video(client, settings, hook)
    assert path2 == path1
    # Cache hit -> no new API calls.
    assert client.submit_hook.call_count == 1


def test_run_pipeline_reports_per_hook_errors(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    settings.core_video_path.write_bytes(b"core")
    hooks = [Hook(index=1, text="good"), Hook(index=2, text="bad")]

    def fake_generate(client, settings, hook):
        if hook.text == "bad":
            raise RuntimeError("heygen exploded")
        path = settings.cache_dir / f"{hook.slug}.mp4"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"hook")
        return path

    def fake_stitch(spec, runner=None):
        spec.output_path.parent.mkdir(parents=True, exist_ok=True)
        spec.output_path.write_bytes(b"final")
        return spec.output_path

    monkeypatch.setattr("reels.pipeline.generate_hook_video", fake_generate)
    monkeypatch.setattr("reels.pipeline.stitch", fake_stitch)

    client = MagicMock()
    results = run_pipeline(hooks, settings, client=client)
    by_index = {r.hook.index: r for r in results}
    assert by_index[1].ok is True
    assert by_index[1].final_path and by_index[1].final_path.exists()
    assert by_index[2].ok is False
    assert "heygen exploded" in (by_index[2].error or "")
