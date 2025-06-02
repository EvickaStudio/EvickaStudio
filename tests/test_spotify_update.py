import spotify_update as su


def test_format_duration() -> None:
    assert su.format_duration(0) == "0:00"
    assert su.format_duration(61000) == "1:01"
    assert su.format_duration(125000) == "2:05"


# def test_create_progress_bar_empty() -> None:
#     bar = su.create_progress_bar(0, 100, width=5)
#     assert set(bar) <= {"▬"}
#     assert len(bar) == 5


def test_create_progress_bar_partial() -> None:
    bar = su.create_progress_bar(50, 100, width=10)
    assert "🔘" in bar
    assert len(bar) == 10


def test_update_readme(tmp_path, monkeypatch) -> None:
    content = "prefix\n<!-- SPOTIFY-START -->\nold\n<!-- SPOTIFY-END -->\nsuffix"  # noqa: E501
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
