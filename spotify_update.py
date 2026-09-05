"""
Update the README Spotify section with current, recent, and top data.
"""

import logging
import os
import sys
import time
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, cast
from urllib.parse import urlsplit

import requests  # type: ignore
import spotipy
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter  # type: ignore
from spotipy.exceptions import SpotifyException, SpotifyOauthError
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


README_PATH = Path(__file__).resolve().with_name("README.md")
START = "<!-- SPOTIFY-START -->"
END = "<!-- SPOTIFY-END -->"


def spotify_link(item: dict[str, Any]) -> str:
    name = escape(str(item.get("name") or "Unknown"))
    url = str((item.get("external_urls") or {}).get("spotify") or "")
    if urlsplit(url).scheme != "https" or urlsplit(url).netloc != "open.spotify.com":
        return name
    return f'<a href="{escape(url, quote=True)}">{name}</a>'


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


def generate_now_playing_block(sp: spotipy.Spotify) -> list[str]:
    current = sp.current_user_playing_track()
    block: list[str] = []
    if not current or not current.get("is_playing") or not current.get("item"):
        return block + ["Not playing anything right now.", ""]

    item = current["item"]
    artists = escape(
        ", ".join(a.get("name", "Unknown") for a in item.get("artists", []))
    )
    album = escape(str((item.get("album") or {}).get("name", "")))
    images = (item.get("album") or {}).get("images") or []
    cover = str(images[0].get("url") or "") if images else ""
    show_cover = urlsplit(cover).scheme == "https" and bool(urlsplit(cover).netloc)
    if show_cover:
        block += [
            f'<img src="{escape(cover, quote=True)}" alt="Album cover: {album}" width="96" align="left" hspace="16" />',
        ]
    block += [
        f"<p><strong>{spotify_link(item)}</strong><br>{artists}<br><sub>{album}</sub></p>",
        "<p>"
        + create_progress_bar(
            int(current.get("progress_ms") or 0), int(item.get("duration_ms") or 0)
        )
        + "</p>",
    ]
    if show_cover:
        block.append('<br clear="left" />')
    return block + [""]


def generate_recently_played_block(sp: spotipy.Spotify) -> list[str]:
    items = sp.current_user_recently_played(limit=RECENTLY_PLAYED_LIMIT).get(
        "items", []
    )
    block = ["### Recently played", ""]
    if not items:
        return block + ["No recently played tracks.", ""]
    block += [
        "<table>",
        (
            '<tr><th align="left">Track / Artist / Album</th>'
            '<th align="left">Played at (UTC)</th></tr>'
        ),
    ]
    for entry in items:
        track = entry.get("track") or {}
        artists = escape(
            ", ".join(a.get("name", "Unknown") for a in track.get("artists", []))
        )
        album = escape(str((track.get("album") or {}).get("name", "")))
        try:
            played_at = datetime.fromisoformat(entry.get("played_at", ""))
            played = played_at.astimezone(UTC).strftime("%d %b %Y · %H:%M")
        except ValueError:
            played = "Unknown time"
        block.append(
            f"<tr><td><strong>{spotify_link(track)}</strong><br>{artists}"
            f"<br><sub>{album}</sub></td><td><sub>{played}</sub></td></tr>"
        )
    return block + ["</table>", ""]


def generate_top_block(sp: spotipy.Spotify) -> list[str]:
    artists = sp.current_user_top_artists(limit=TOP_LIMIT, time_range="short_term").get(
        "items", []
    )
    tracks = sp.current_user_top_tracks(limit=TOP_LIMIT, time_range="short_term").get(
        "items", []
    )
    block = [
        "### On repeat",
        "",
        "Short-term listening.",
        "",
        "<table>",
        (
            '<tr><th scope="col">Rank</th><th align="left" scope="col">Artists</th>'
            '<th align="left" scope="col">Tracks</th></tr>'
        ),
    ]
    for index in range(max(len(artists), len(tracks))):
        artist = spotify_link(artists[index]) if index < len(artists) else "—"
        track = spotify_link(tracks[index]) if index < len(tracks) else "—"
        block.append(
            f"<tr><td><samp>{index + 1:02}</samp></td><td>{artist}</td><td>{track}</td></tr>"
        )
    if not artists and not tracks:
        block.append('<tr><td colspan="3">No top listening data available.</td></tr>')
    return block + ["</table>", ""]


def generate_markdown() -> str:
    """Fetch a complete snapshot; failures leave the previous README untouched."""
    sp = get_spotify_client()
    parts = generate_now_playing_block(sp)
    parts.extend(generate_recently_played_block(sp))
    parts.extend(generate_top_block(sp))
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    parts.append(f"<sub>{now}</sub>")
    return "\n".join(parts)


def update_readme(path: Path = README_PATH) -> None:
    """Replace only the single marked block, atomically and without regex expansion."""
    content = path.read_text(encoding="utf-8")
    if content.count(START) != 1 or content.count(END) != 1:
        raise ValueError("README must contain exactly one pair of Spotify markers")
    before, rest = content.split(START)
    if END not in rest:
        raise ValueError("Spotify markers are out of order")
    _, after = rest.split(END)
    snippet = generate_markdown()
    updated = before + START + "\n" + snippet + "\n" + END + after
    if updated == content:
        return
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as file:
            temporary = Path(file.name)
            file.write(updated)
        temporary.chmod(path.stat().st_mode)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    logger.info("README updated successfully")


if __name__ == "__main__":
    try:
        update_readme()
    except ValueError:
        logger.exception("Invalid configuration or README format")
        sys.exit(1)
    except (RuntimeError, SpotifyException, requests.RequestException):
        logger.error("Spotify update failed; previous README preserved")
        sys.exit(1)
    except OSError:
        logger.exception("File operation failed")
        sys.exit(1)
