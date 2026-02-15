import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import spotify_update as su  # noqa: E402


def test_format_duration() -> None:
    assert su.format_duration(0) == "0:00"
    assert su.format_duration(61000) == "1:01"
    assert su.format_duration(125000) == "2:05"


def test_create_progress_bar_empty() -> None:
    bar = su.create_progress_bar(0, 100_000, width=10)
    assert "░" * 10 in bar
    assert "`0:00`" in bar


def test_create_progress_bar_half() -> None:
    bar = su.create_progress_bar(50_000, 100_000, width=10)
    assert "▓" * 5 in bar
    assert "░" * 5 in bar


def test_create_progress_bar_full() -> None:
    bar = su.create_progress_bar(100_000, 100_000, width=10)
    assert "▓" * 10 in bar
    assert "░" not in bar


def test_create_progress_bar_zero_duration() -> None:
    bar = su.create_progress_bar(50_000, 0, width=10)
    assert "░" * 10 in bar


def test_update_readme(tmp_path, monkeypatch) -> None:
    content = (
        "prefix\n"
        "<!-- SPOTIFY-START -->\nold\n<!-- SPOTIFY-END -->\n"
        "suffix"
    )
    readme = tmp_path / "README.md"
    readme.write_text(content, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "secret")
    monkeypatch.setenv("SPOTIFY_REFRESH_TOKEN", "token")
    monkeypatch.setattr(su, "generate_markdown", lambda: "new")
    su.update_readme()
    updated = readme.read_text(encoding="utf-8")
    assert "<!-- SPOTIFY-START -->\nnew\n<!-- SPOTIFY-END -->" in updated
    assert "prefix" in updated
    assert "suffix" in updated
