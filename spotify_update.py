#!/usr/bin/env python3
"""
Update the README Spotify section with current, recent, and top data.
"""

import logging
import os
import re
import sys
import time
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import List
from typing import cast

import requests  # type: ignore
import spotipy
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter  # type: ignore
from spotipy.exceptions import SpotifyException
from spotipy.exceptions import SpotifyOauthError
from spotipy.oauth2 import SpotifyOAuth
from urllib3.util.retry import Retry

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

SCOPE = "user-read-currently-playing user-read-recently-played user-top-read"
REDIRECT_URI = os.getenv(
    "SPOTIFY_REDIRECT_URI",
    "http://127.0.0.1:8888/callback",
)
RECENTLY_PLAYED_LIMIT = int(os.getenv("SPOTIFY_RECENTLY_PLAYED_LIMIT", "5"))
TOP_LIMIT = int(os.getenv("SPOTIFY_TOP_LIMIT", "5"))
PROGRESS_BAR_WIDTH = int(os.getenv("SPOTIFY_PROGRESS_BAR_WIDTH", "20"))

MAX_AUTH_RETRIES = int(os.getenv("SPOTIFY_AUTH_RETRIES", "4"))
AUTH_RETRY_BASE_DELAY = float(os.getenv("SPOTIFY_AUTH_RETRY_BASE_DELAY", "5"))


def icon_tag(name: str, alt: str) -> str:
    """
    Return single-variant icon HTML using local SVG assets.
    """
    return f'<img src="./assets/icons/{name}.svg" width="16" alt="{alt}">'


def section_heading(icon_name: str, title: str) -> str:
    """
    Build a markdown heading with a dark/light mode icon.
    """
    return f"### {icon_tag(icon_name, title)} {title}"


def rank_prefix(index: int) -> str:
    """
    Build icon-based ranking prefix for top lists.
    """
    rank = index + 1
    return f"{icon_tag('disc3', f'Rank {rank}')} **#{rank}**"


def _require_env(name: str) -> str:
    """
    Return required environment variable, otherwise raise ValueError.
    """
    if value := os.getenv(name):
        return value
    raise ValueError(f"Missing required environment variable: {name}")


def _build_retry_session() -> requests.Session:
    """
    Build requests session for Spotify API calls with retries.
    """
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get_spotify_client() -> spotipy.Spotify:
    """
    Return authenticated Spotify client with resilient token refresh.
    """
    client_id = _require_env("SPOTIFY_CLIENT_ID")
    client_secret = _require_env("SPOTIFY_CLIENT_SECRET")
    refresh_token = _require_env("SPOTIFY_REFRESH_TOKEN")

    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        show_dialog=False,
    )

    last_error: SpotifyOauthError | requests.RequestException | None = None
    token_info: dict[str, Any] | None = None

    for attempt in range(1, MAX_AUTH_RETRIES + 1):
        try:
            token_info = cast(
                dict[str, Any],
                auth_manager.refresh_access_token(refresh_token),
            )
            break
        except SpotifyOauthError as exc:
            last_error = exc
        except requests.RequestException as exc:
            last_error = exc

        if attempt < MAX_AUTH_RETRIES:
            delay = AUTH_RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.warning(
                "Spotify token refresh failed (attempt %d/%d): %s. "
                "Retrying in %.1f seconds.",
                attempt,
                MAX_AUTH_RETRIES,
                last_error,
                delay,
            )
            time.sleep(delay)

    if token_info is None:
        raise RuntimeError(
            f"Spotify token refresh failed after {MAX_AUTH_RETRIES} attempts"
        ) from last_error

    access_token = token_info.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise RuntimeError("Spotify token refresh returned invalid access token")

    session = _build_retry_session()
    return spotipy.Spotify(auth=access_token, requests_session=session)


def format_duration(ms: int) -> str:
    """
    Convert milliseconds to `M:SS` format.
    """
    minutes = ms // 60_000
    seconds = (ms % 60_000) // 1_000
    return f"{minutes}:{seconds:02d}"


def format_relative_time(played_at: str) -> str:
    """
    Convert Spotify played_at timestamp into a short relative label.
    """
    try:
        played_dt = datetime.fromisoformat(played_at.replace("Z", "+00:00"))
    except ValueError:
        return "unknown time"

    delta = datetime.now(timezone.utc) - played_dt.astimezone(timezone.utc)
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago"

    hours = minutes // 60
    if hours < 24:
        return f"{hours} h ago"

    days = hours // 24
    return f"{days} d ago"


def create_progress_bar(
    progress_ms: int,
    duration_ms: int,
    width: int = PROGRESS_BAR_WIDTH,
) -> str:
    """
    Create a markdown-safe progress bar for GitHub README rendering.
    """
    if width < 1:
        raise ValueError("Progress bar width must be greater than zero")

    progress_percent = 0.0
    if duration_ms > 0 and progress_ms > 0:
        progress_percent = min(max(progress_ms / duration_ms, 0.0), 1.0)

    filled = round(progress_percent * width)
    bar = "▓" * filled + "░" * (width - filled)
    return (
        f"<code>{format_duration(progress_ms)}</code> "
        f"{bar} "
        f"<code>{format_duration(duration_ms)}</code>"
    )


def generate_now_playing_block(sp: spotipy.Spotify) -> List[str]:
    """
    Generate markdown lines for the "Now Playing" section.
    """
    block: List[str] = [
        "",
        section_heading("play-circle", "Now Playing"),
        "",
    ]
    try:
        current = cast(dict[str, Any] | None, sp.current_user_playing_track())
        if not current or not current.get("is_playing"):
            block.extend(["> *Not playing anything right now.*", ""])
            return block

        item = cast(dict[str, Any], current.get("item") or {})
        name = cast(str, item.get("name", "Unknown"))
        artists = ", ".join(
            cast(str, artist.get("name", "Unknown"))
            for artist in cast(list[dict[str, Any]], item.get("artists", []))
        )
        external_urls = cast(dict[str, Any], item.get("external_urls", {}))
        url = cast(str, external_urls.get("spotify", ""))
        album_data = cast(dict[str, Any], item.get("album", {}))
        album = cast(str, album_data.get("name", ""))
        images = cast(
            list[dict[str, Any]],
            album_data.get("images", []),
        )
        cover = cast(str, images[0].get("url", "")) if images else ""
        duration_ms = int(item.get("duration_ms", 0))
        progress_ms = int(current.get("progress_ms", 0))

        if cover:
            block.extend(
                [
                    '<p align="center">',
                    f'  <img src="{cover}" alt="" width="120" />',
                    "</p>",
                    "",
                ]
            )

        block.extend(
            [
                f"**[{name}]({url})**",
                f"*by* **{artists}**",
                f"*Album:* {album}",
                "",
                (
                    '<p align="center">'
                    f"{create_progress_bar(progress_ms, duration_ms)}"
                    "</p>"
                ),
                "",
            ]
        )
    except (
        SpotifyException,
        requests.RequestException,
        TypeError,
        ValueError,
    ) as exc:
        logger.exception("Could not fetch now playing block")
        block.extend([f"> ⚠️ Could not fetch now playing data: `{exc}`", ""])
    return block


def generate_recently_played_block(sp: spotipy.Spotify) -> List[str]:
    """
    Generate markdown lines for "Recently Played" section.
    """
    block: List[str] = ["", section_heading("history", "Recently Played"), ""]
    try:
        results = cast(
            dict[str, Any],
            sp.current_user_recently_played(limit=RECENTLY_PLAYED_LIMIT),
        )
        items = cast(list[dict[str, Any]], results.get("items", []))
        if not items:
            block.extend(["> No recently played tracks.", ""])
            return block

        for entry in items:
            track = cast(dict[str, Any], entry.get("track", {}))
            name = cast(str, track.get("name", "Unknown"))
            artists_data = cast(list[dict[str, Any]], track.get("artists", []))
            artists = ", ".join(
                cast(str, artist.get("name", "Unknown")) for artist in artists_data
            )
            external_urls = cast(
                dict[str, Any],
                track.get("external_urls", {}),
            )
            url = cast(str, external_urls.get("spotify", ""))
            album_data = cast(dict[str, Any], track.get("album", {}))
            album = cast(str, album_data.get("name", ""))
            played_at = cast(str, entry.get("played_at", ""))
            played_ago = format_relative_time(played_at)
            block.append(
                f"- **[{name}]({url})** by **{artists}** *({album})* - `{played_ago}`"
            )

        block.append("")
    except (
        SpotifyException,
        requests.RequestException,
        TypeError,
        ValueError,
    ) as exc:
        logger.exception("Could not fetch recently played block")
        block.extend([f"> ⚠️ Could not fetch recently played data: `{exc}`", ""])
    return block


def generate_top_artists_block(sp: spotipy.Spotify) -> List[str]:
    """
    Generate markdown lines for "Top Artists" section.
    """
    block: List[str] = [
        "",
        section_heading("users", "Top Artists *(Short Term)*"),
        "",
    ]
    try:
        results = cast(
            dict[str, Any],
            sp.current_user_top_artists(
                limit=TOP_LIMIT,
                time_range="short_term",
            ),
        )
        items = cast(list[dict[str, Any]], results.get("items", []))
        if not items:
            block.extend(["> No top artists data available.", ""])
            return block

        for index, artist in enumerate(items):
            name = cast(str, artist.get("name", "Unknown"))
            url = cast(
                str,
                cast(dict[str, Any], artist.get("external_urls", {})).get(
                    "spotify",
                    "",
                ),
            )
            block.append(f"- {rank_prefix(index)} [**{name}**]({url})")

        block.append("")
    except (
        SpotifyException,
        requests.RequestException,
        TypeError,
        ValueError,
    ) as exc:
        logger.exception("Could not fetch top artists block")
        block.extend([f"> ⚠️ Could not fetch top artists: `{exc}`", ""])
    return block


def generate_top_tracks_block(sp: spotipy.Spotify) -> List[str]:
    """
    Generate markdown lines for "Top Tracks" section.
    """
    block: List[str] = [
        "",
        section_heading("list-music", "Top Tracks *(Short Term)*"),
        "",
    ]
    try:
        results = cast(
            dict[str, Any],
            sp.current_user_top_tracks(
                limit=TOP_LIMIT,
                time_range="short_term",
            ),
        )
        items = cast(list[dict[str, Any]], results.get("items", []))
        if not items:
            block.extend(["> No top tracks data available.", ""])
            return block

        for index, track in enumerate(items):
            name = cast(str, track.get("name", "Unknown"))
            url = cast(
                str,
                cast(dict[str, Any], track.get("external_urls", {})).get(
                    "spotify",
                    "",
                ),
            )
            block.append(f"- {rank_prefix(index)} [**{name}**]({url})")

        block.append("")
    except (
        SpotifyException,
        requests.RequestException,
        TypeError,
        ValueError,
    ) as exc:
        logger.exception("Could not fetch top tracks block")
        block.extend([f"> ⚠️ Could not fetch top tracks: `{exc}`", ""])
    return block


def generate_markdown() -> str:
    """
    Generate complete Spotify markdown snippet.
    """
    sp = get_spotify_client()
    parts: List[str] = [
        section_heading("music", "Spotify"),
    ]
    parts.extend(generate_now_playing_block(sp))
    parts.extend(generate_recently_played_block(sp))
    parts.extend(generate_top_artists_block(sp))
    parts.extend(generate_top_tracks_block(sp))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    parts.append(f"{icon_tag('clock3', 'Last updated')} *Last updated: {now}*")
    return "\n".join(parts)


def update_readme() -> None:
    """
    Replace content between Spotify sentinels in README.
    """
    snippet = generate_markdown()
    path = os.path.join(os.getcwd(), "README.md")

    try:
        with open(path, "r", encoding="utf-8") as file:
            content = file.read()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"README not found at {path}") from exc

    pattern = re.compile(
        r"(<!-- SPOTIFY-START -->).*?(<!-- SPOTIFY-END -->)",
        re.DOTALL,
    )
    if not pattern.search(content):
        raise ValueError("Spotify sentinel comments not found in README")

    updated = pattern.sub(rf"\1\n{snippet}\n\2", content)
    with open(path, "w", encoding="utf-8") as file:
        file.write(updated)

    logger.info("README updated successfully")


if __name__ == "__main__":
    try:
        update_readme()
    except ValueError:
        logger.exception("Invalid configuration or README format")
        sys.exit(1)
    except RuntimeError:
        logger.exception("Spotify update failed")
        sys.exit(1)
    except OSError:
        logger.exception("File operation failed")
        sys.exit(1)
