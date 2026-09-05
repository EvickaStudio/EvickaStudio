import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import spotify_update as su


def test_update_readme(tmp_path, monkeypatch) -> None:
    content = "prefix\n<!-- SPOTIFY-START -->\nold\n<!-- SPOTIFY-END -->\nsuffix"
    readme = tmp_path / "README.md"
    readme.write_text(content, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "secret")
    monkeypatch.setenv("SPOTIFY_REFRESH_TOKEN", "token")
    monkeypatch.setattr(
        su, "generate_snapshot", lambda: ("new", {"now-playing.svg": "<svg/>"})
    )
    su.update_readme(readme)
    updated = readme.read_text(encoding="utf-8")
    assert "<!-- SPOTIFY-START -->\nnew\n<!-- SPOTIFY-END -->" in updated
    assert "prefix" in updated
    assert "suffix" in updated
    assert (tmp_path / "assets/generated/now-playing.svg").read_text() == "<svg/>"


def test_update_preserves_copy_and_literal_backslashes(tmp_path, monkeypatch):
    readme = tmp_path / "README.md"
    before = "Handwritten: ä & <strong>text</strong>\n"
    after = "\nHandwritten ending.\n"
    readme.write_text(before + su.START + "old" + su.END + after)
    snippet = r"Music \1 \g<2> \new"
    monkeypatch.setattr(su, "generate_snapshot", lambda: (snippet, {}))
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
    monkeypatch.setattr(su, "generate_snapshot", lambda: pytest.fail("must not fetch"))
    with pytest.raises(ValueError):
        su.update_readme(readme)
    assert readme.read_text() == content


def test_fetch_failure_preserves_snapshot(tmp_path, monkeypatch):
    readme = tmp_path / "README.md"
    content = su.START + "last good snapshot" + su.END
    readme.write_text(content)

    def fail():
        raise su.requests.RequestException("offline")

    monkeypatch.setattr(su, "generate_snapshot", fail)
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
    snippet, assets = su.generate_snapshot()
    assert "A &lt; B &amp; C" in snippet
    assert "Artist &amp; friend" in snippet
    assert "&lt;Album&gt;" in snippet
    assert "now-playing.svg" in assets
    assert "recently-played.svg" in assets
    assert "on-repeat.svg" in assets
    assert "<table>" not in snippet
    assert "assets/icons" not in snippet
    assert "### Spotify" not in snippet
    assert (
        su.spotify_link(
            {"name": "<bad>", "external_urls": {"spotify": "javascript:alert(1)"}}
        )
        == "&lt;bad&gt;"
    )
    sp.current_user_playing_track.return_value = None
    assert "Not playing" in "\n".join(su.generate_now_playing_block(sp)[0])


@pytest.mark.parametrize(
    "cover", ["https://i.scdn.co/image/example?a=1&b=2", "", "javascript:alert(1)"]
)
def test_album_cover(cover, monkeypatch):
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
    response = Mock()
    response.status_code = 200
    response.headers = {"Content-Type": "image/jpeg"}
    response.content = b"cover"
    fetch = Mock(return_value=response)
    monkeypatch.setattr(su.requests, "get", fetch)
    lines, assets = su.generate_now_playing_block(sp)
    block = "\n".join(lines)
    svg = assets["now-playing.svg"]
    if cover.startswith("https:"):
        assert "data:image/jpeg;base64,Y292ZXI=" in svg
        fetch.assert_called_once_with(cover, timeout=15, allow_redirects=False)
    else:
        assert "<image" not in svg
        fetch.assert_not_called()
    assert "&quot;quoted&quot;" in block
    assert "<table" not in block
    assert "Track" in block


def test_svg_layout_and_escaping():
    from xml.etree import ElementTree as ET

    from profile_cards import (
        render_now_playing,
        render_on_repeat,
        render_recently_played,
        render_technologies,
    )

    current = {
        "is_playing": True,
        "progress_ms": 200000,
        "item": {
            "name": "<Title> & " + "Long " * 40,
            "duration_ms": 100000,
            "artists": [{"name": "A & B"}],
            "album": {"name": "<Album>"},
        },
    }
    ns = {"s": "http://www.w3.org/2000/svg"}
    for compact in (False, True):
        svg = render_now_playing(current, compact=compact)
        root = ET.fromstring(svg)
        assert "<Title> & Long" in root.find("s:title", ns).text
        title_lines = root.findall("s:text[@class='title']", ns)
        assert len(title_lines) == 2
        assert title_lines[-1].text.endswith("…")
        rail = root.find("s:rect[@class='rail']", ns)
        progress = root.find("s:rect[@class='accent']", ns)
        assert float(rail.attrib["width"]) == float(progress.attrib["width"])
        assert "prefers-color-scheme: dark" in svg
        assert "linearGradient" not in svg
        assert 'opacity=".6"' in render_now_playing(
            current, "data:image/jpeg;base64,Y292ZXI=", compact
        )
        assert 'preserveAspectRatio="xMidYMid slice"' in render_now_playing(
            current, "data:image/jpeg;base64,Y292ZXI=", compact
        )
        assert "<script" not in svg and "foreignObject" not in svg
        tech = ET.fromstring(render_technologies(compact))
        assert "Rust" in "".join(tech.itertext())
        assert "Windows" in "".join(tech.itertext())
        assert "Not playing" in render_now_playing(None, compact=compact)

        # Test render_recently_played
        rp_items = [
            {
                "track": {
                    "name": "<Song & Dance>",
                    "artists": [{"name": "X & Y"}],
                    "album": {"name": "Album & Co"},
                },
                "played_at": "2026-09-05T18:00:00Z",
            }
        ]
        rp_svg = render_recently_played(
            rp_items, ["data:image/jpeg;base64,Y292ZXI="], compact=compact
        )
        rp_root = ET.fromstring(rp_svg)
        assert "<Song & Dance>" in rp_root.find("s:title", ns).text
        assert "<script" not in rp_svg and "foreignObject" not in rp_svg
        assert "No recently played" in render_recently_played([], compact=compact)

        # Test render_on_repeat
        top_tracks = [
            {
                "name": "<Top & Track>",
                "artists": [{"name": "A & B"}],
                "album": {"name": "Top Album"},
            }
        ]
        top_artists = [{"name": "<Top & Artist>", "genres": ["indie rock"]}]
        or_svg = render_on_repeat(
            top_tracks,
            top_artists,
            ["data:image/jpeg;base64,Y292ZXI="],
            ["data:image/jpeg;base64,Y292ZXI="],
            compact=compact,
        )
        or_root = ET.fromstring(or_svg)
        assert "<Top & Track>" in or_root.find("s:title", ns).text
        assert "<script" not in or_svg and "foreignObject" not in or_svg
        assert "01" in "".join(or_root.itertext())
    current["item"]["duration_ms"] = 0
    root = ET.fromstring(render_now_playing(current))
    assert float(root.find("s:rect[@class='accent']", ns).attrib["width"]) == 0


def test_late_api_failure_preserves_cards_and_readme(tmp_path, monkeypatch):
    from unittest.mock import Mock

    readme = tmp_path / "README.md"
    content = su.START + "old" + su.END
    readme.write_text(content)
    asset = tmp_path / "assets" / "generated" / "now-playing.svg"
    asset.parent.mkdir(parents=True)
    asset.write_text("previous card")
    sp = Mock()
    sp.current_user_playing_track.return_value = None
    sp.current_user_recently_played.side_effect = su.requests.RequestException(
        "offline"
    )
    monkeypatch.setattr(su, "get_spotify_client", lambda: sp)
    with pytest.raises(su.requests.RequestException):
        su.update_readme(readme)
    assert readme.read_text() == content
    assert asset.read_text() == "previous card"
