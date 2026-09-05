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
        su, "generate_snapshot", lambda: ("new", {"spotify.svg": "<svg/>"})
    )
    su.update_readme(readme)
    updated = readme.read_text(encoding="utf-8")
    assert "<!-- SPOTIFY-START -->\nnew\n<!-- SPOTIFY-END -->" in updated
    assert "prefix" in updated
    assert "suffix" in updated
    assert (tmp_path / "assets/generated/spotify.svg").read_text() == "<svg/>"


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
    sp.current_user.return_value = {
        "external_urls": {"spotify": "https://open.spotify.com/user/example"}
    }
    monkeypatch.setattr(su, "get_spotify_client", lambda: sp)
    snippet, assets = su.generate_snapshot()
    assert "A &lt; B &amp; C" in snippet
    assert "Artist &amp; friend" in snippet
    assert "&lt;Album&gt;" in snippet
    assert set(assets) == {
        "spotify.svg",
        "spotify-mobile.svg",
        "technologies.svg",
        "technologies-mobile.svg",
    }
    assert snippet.count("<picture>") == snippet.count("<img ") == 1
    assert 'src="assets/generated/spotify.svg"' in snippet
    assert 'srcset="assets/generated/spotify-mobile.svg"' in snippet
    assert 'href="https://open.spotify.com/user/example"' in snippet
    sp.current_user.assert_called_once_with()
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
    sp.current_user.return_value = {"external_urls": {"spotify": "javascript:alert(1)"}}
    snippet, assets = su.generate_snapshot()
    assert "Not playing" in snippet
    assert 'href="https://open.spotify.com/"' in snippet
    assert "javascript:" not in snippet
    assert "Last listened" in assets["spotify.svg"]
    assert "A &lt; B &amp; C" in assets["spotify.svg"]


@pytest.mark.parametrize(
    "cover", ["https://i.scdn.co/image/example?a=1&b=2", "", "javascript:alert(1)"]
)
def test_album_cover(cover, monkeypatch):
    from unittest.mock import Mock

    sp = Mock()
    sp.requests_session = None
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
    sp.current_user_recently_played.return_value = {"items": []}
    sp.current_user_top_tracks.return_value = {"items": []}
    sp.current_user_top_artists.return_value = {"items": []}
    sp.current_user.return_value = {}
    monkeypatch.setattr(su, "get_spotify_client", lambda: sp)
    response = Mock()
    response.status_code = 200
    response.headers = {"Content-Type": "image/jpeg"}
    response.content = b"cover"
    fetch = Mock(return_value=response)
    monkeypatch.setattr(su.requests, "get", fetch)
    block, assets = su.generate_snapshot()
    svg = assets["spotify.svg"]
    if cover.startswith("https:"):
        assert "data:image/jpeg;base64,Y292ZXI=" in svg
        fetch.assert_called_once_with(cover, timeout=15, allow_redirects=False)
    else:
        assert "<image" not in svg
        fetch.assert_not_called()
    assert "&quot;quoted&quot;" in block
    assert "<table" not in block
    assert "Track" in block


@pytest.mark.parametrize("compact", [False, True])
def test_svg_layout_and_escaping(compact):
    from xml.etree import ElementTree as ET

    from profile_cards import format_played_at, render_spotify, render_technologies

    track = {
        "name": "<Title> & " + "Long " * 40,
        "duration_ms": 100000,
        "artists": [{"name": "A & B"}],
        "album": {"name": "<Album>"},
    }
    current = {"is_playing": True, "progress_ms": 25000, "item": track}
    recent = [{"track": track, "played_at": "2026-09-05T20:00:00+02:00"}]
    artists = [{"name": "<Top & Artist>", "genres": ["indie rock"]}]
    cover = "data:image/jpeg;base64,Y292ZXI="
    ns = {"s": "http://www.w3.org/2000/svg"}
    svg = render_spotify(
        current,
        recent,
        [track],
        artists,
        cover,
        [cover],
        [cover],
        [cover],
        "2026-09-05 19:00 UTC",
        compact=compact,
    )
    root = ET.fromstring(svg)
    title = root.find("s:title", ns).text
    assert track["name"] in title and artists[0]["name"] in title
    hero = root.find(".//s:g[@id='now-playing']", ns)
    assert hero.find("s:image", ns) is not None
    assert "equalizer" not in svg and "artwork-drift" not in svg
    assert "prefers-reduced-motion: no-preference" in svg
    assert "animation: playback 75s linear forwards;" in svg
    assert "infinite" not in svg
    title_lines = hero.findall(".//s:text[@class='title']", ns)
    assert len(title_lines) == 2
    assert title_lines[-1].text.endswith("…")
    rail = root.find(".//s:rect[@id='playback-rail']", ns)
    progress = root.find(".//s:rect[@id='playback-progress']", ns)
    assert float(progress.attrib["width"]) == float(rail.attrib["width"]) / 4
    assert f"to {{ width: {rail.attrib['width']}px; }}" in svg
    assert 'opacity=".6"' in svg
    assert 'preserveAspectRatio="xMidYMid slice"' in svg
    assert "<script" not in svg and "foreignObject" not in svg
    assert not any(
        node.text in {"SPOTIFY", "NOW PLAYING"}
        for node in root.findall(".//s:text", ns)
    )
    assert len(root.findall(".//s:image", ns)) == 4
    recent_section = root.find(".//s:g[@id='recently-played']", ns)
    assert "UTC" not in "".join(recent_section.itertext())
    assert "05 Sep · 18:00" not in svg
    assert "Updated 2026-09-05 19:00 UTC" in svg
    assert format_played_at("not-a-date") == ""

    # Every section shares the same surface, and metadata has bounded viewports.
    for section in ("now-playing", "recently-played", "on-repeat", "top-artists"):
        assert root.find(f".//s:g[@id='{section}']", ns) is not None
    ids = [element.attrib["id"] for element in root.iter() if "id" in element.attrib]
    assert len(ids) == len(set(ids))
    for viewport in root.findall(".//s:svg", ns):
        assert int(viewport.attrib["x"]) + int(viewport.attrib["width"]) <= int(
            root.attrib["width"]
        )
        assert int(viewport.attrib["y"]) + int(viewport.attrib["height"]) <= int(
            root.attrib["height"]
        )

    for duration, elapsed, fraction, remaining in (
        (0, 200000, 0, 0),
        (100000, -1, 0, 100),
        (100000, 200000, 1, 0),
        (100000, 99999, 0.99999, 0.001),
    ):
        track["duration_ms"] = duration
        current["progress_ms"] = elapsed
        svg = render_spotify(current, [], [], [], compact=compact)
        root = ET.fromstring(svg)
        assert float(
            root.find(".//s:rect[@id='playback-progress']", ns).attrib["width"]
        ) == pytest.approx(float(rail.attrib["width"]) * fraction, abs=0.005)
        if remaining:
            assert f"animation: playback {remaining:g}s linear forwards;" in svg
        else:
            assert "animation:" not in svg

    current["is_playing"] = False
    paused = render_spotify(current, [], [], [], compact=compact)
    assert "Paused" in paused
    assert "animation:" not in paused
    idle = render_spotify(None, recent, [], [], cover, compact=compact)
    assert "Last listened" in idle and "<image" in idle
    assert "playback-progress" not in idle
    empty = render_spotify(None, [], [], [], compact=compact)
    ET.fromstring(empty)
    assert all(
        label in empty
        for label in (
            "Not playing",
            "No recently played",
            "No top tracks",
            "No top artists",
        )
    )
    tech = ET.fromstring(render_technologies(compact))
    assert "Rust" in "".join(tech.itertext())
    assert "Windows" in "".join(tech.itertext())


def test_late_api_failure_preserves_cards_and_readme(tmp_path, monkeypatch):
    from unittest.mock import Mock

    readme = tmp_path / "README.md"
    content = su.START + "old" + su.END
    readme.write_text(content)
    asset = tmp_path / "assets" / "generated" / "spotify.svg"
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
