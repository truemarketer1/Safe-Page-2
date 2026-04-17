from pathlib import Path

from reels.hooks_source import Hook, read_csv_hooks


def test_read_csv_with_header(tmp_path: Path) -> None:
    csv = tmp_path / "hooks.csv"
    csv.write_text("hook\nFirst hook\nSecond hook\n")
    hooks = read_csv_hooks(csv)
    assert [h.text for h in hooks] == ["First hook", "Second hook"]
    assert [h.index for h in hooks] == [1, 2]


def test_read_csv_without_header(tmp_path: Path) -> None:
    csv = tmp_path / "hooks.csv"
    csv.write_text("Only hook\nAnother one\n")
    hooks = read_csv_hooks(csv)
    assert [h.text for h in hooks] == ["Only hook", "Another one"]


def test_read_csv_skips_blank_rows(tmp_path: Path) -> None:
    csv = tmp_path / "hooks.csv"
    csv.write_text("hook\nFirst\n\n   \nSecond\n")
    hooks = read_csv_hooks(csv)
    assert [h.text for h in hooks] == ["First", "Second"]


def test_hook_slug_is_filesystem_safe() -> None:
    h = Hook(index=3, text="Stop eating less! Start eating smarter.")
    assert h.slug.startswith("003_")
    assert all(c.isalnum() or c == "_" for c in h.slug)
