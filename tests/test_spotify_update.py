import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import spotify_update as su


def test_format_duration() -> None:
    assert su.format_duration(0) == "0:00"
    assert su.format_duration(61000) == "1:01"
    assert su.format_duration(125000) == "2:05"


def test_create_progress_bar_empty() -> None:
    bar = su.create_progress_bar(0, 100_000, width=10)
    assert "░" * 10 in bar
    assert "<code>0:00</code>" in bar


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
    content = "prefix\n<!-- SPOTIFY-START -->\nold\n<!-- SPOTIFY-END -->\nsuffix"
    readme = tmp_path / "README.md"
    readme.write_text(content, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "secret")
    monkeypatch.setenv("SPOTIFY_REFRESH_TOKEN", "token")
    monkeypatch.setattr(su, "generate_markdown", lambda: "new")
    su.update_readme(readme)
    updated = readme.read_text(encoding="utf-8")
    assert "<!-- SPOTIFY-START -->\nnew\n<!-- SPOTIFY-END -->" in updated
    assert "prefix" in updated
    assert "suffix" in updated


def test_update_preserves_copy_and_literal_backslashes(tmp_path, monkeypatch):
    readme = tmp_path / "README.md"
    before = "Handwritten: ä & <strong>text</strong>\n"
    after = "\nHandwritten ending.\n"
    readme.write_text(before + su.START + "old" + su.END + after)
    snippet = r"Music \1 \g<2> \new"
    monkeypatch.setattr(su, "generate_markdown", lambda: snippet)
    su.update_readme(readme)
    assert (
        readme.read_text() == before + su.START + "\n" + snippet + "\n" + su.END + after
    )


@pytest.mark.parametrize(
    "content", ["no markers", su.END + su.START, su.START * 2 + su.END]
)
def test_invalid_markers_do_not_fetch_or_write(tmp_path, monkeypatch, content):
    readme = tmp_path / "README.md"
    readme.write_text(content)
    monkeypatch.setattr(su, "generate_markdown", lambda: pytest.fail("must not fetch"))
    with pytest.raises(ValueError):
        su.update_readme(readme)
    assert readme.read_text() == content


def test_fetch_failure_preserves_snapshot(tmp_path, monkeypatch):
    readme = tmp_path / "README.md"
    content = su.START + "last good snapshot" + su.END
    readme.write_text(content)

    def fail():
        raise su.requests.RequestException("offline")

    monkeypatch.setattr(su, "generate_markdown", fail)
    with pytest.raises(su.requests.RequestException):
        su.update_readme(readme)
    assert readme.read_text() == content


def test_snapshot_rendering(monkeypatch):
    from unittest.mock import Mock

    track = {
        "name": "A < B & C",
        "external_urls": {"spotify": "https://open.spotify.com/track/example"},
        "artists": [{"name": "Artist & friend"}],
        "album": {"name": "<Album>"},
        "duration_ms": 120000,
    }
    sp = Mock()
    sp.current_user_playing_track.return_value = {
        "is_playing": True,
        "item": track,
        "progress_ms": 60000,
    }
    sp.current_user_recently_played.return_value = {
        "items": [{"track": track, "played_at": "2026-09-05T12:00:00Z"}]
    }
    sp.current_user_top_artists.return_value = {"items": []}
    sp.current_user_top_tracks.return_value = {"items": [track]}
    monkeypatch.setattr(su, "get_spotify_client", lambda: sp)
    snippet = su.generate_markdown()
    assert "A &lt; B &amp; C" in snippet
    assert "Artist &amp; friend" in snippet
    assert "&lt;Album&gt;" in snippet
    assert "05 Sep 2026 · 12:00" in snippet
    assert "<td>—</td>" in snippet
    assert snippet.count("<table>") == 2
    assert "assets/icons" not in snippet
    assert "### Spotify" not in snippet
    assert (
        su.spotify_link(
            {"name": "<bad>", "external_urls": {"spotify": "javascript:alert(1)"}}
        )
        == "&lt;bad&gt;"
    )
    sp.current_user_playing_track.return_value = None
    assert "Not playing" in "\n".join(su.generate_now_playing_block(sp))


@pytest.mark.parametrize(
    "cover", ["https://i.scdn.co/image/example?a=1&b=2", "", "javascript:alert(1)"]
)
def test_album_cover(cover):
    from unittest.mock import Mock

    sp = Mock()
    sp.current_user_playing_track.return_value = {
        "is_playing": True,
        "item": {
            "name": "Track",
            "album": {
                "name": 'A "quoted" album',
                "images": [{"url": cover}] if cover else [],
            },
        },
    }
    block = "\n".join(su.generate_now_playing_block(sp))
    if cover.startswith("https:"):
        assert 'src="https://i.scdn.co/image/example?a=1&amp;b=2"' in block
        assert 'alt="Album cover: A &quot;quoted&quot; album"' in block
        assert 'align="left"' in block
        assert '<br clear="left" />' in block
    else:
        assert "<img" not in block
        assert "<table" not in block
    assert "<table" not in block
    assert "Track" in block
