"""
Update the README Spotify section with current, recent, and top data.
"""

import base64
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

from profile_cards import (
    picture,
    render_now_playing,
    render_on_repeat,
    render_recently_played,
    render_technologies,
)

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


def fetch_image_base64(
    url: str, session: requests.Session | None = None, timeout: int = 15
) -> str:
    if not url:
        return ""
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != "i.scdn.co":
        return ""
    try:
        getter = session.get if session is not None else requests.get
        response = getter(url, timeout=timeout, allow_redirects=False)
        response.raise_for_status()
        mime = response.headers.get("Content-Type", "").split(";")[0]
        if response.status_code == 200 and mime in ("image/jpeg", "image/png"):
            return f"data:{mime};base64," + base64.b64encode(response.content).decode(
                "ascii"
            )
    except (requests.RequestException, OSError):
        return ""
    return ""


def pick_image_url(images: list[dict[str, Any]], target: int = 64) -> str:
    if not images:
        return ""
    chosen = min(images, key=lambda img: abs((img.get("width") or 0) - target))
    return str(chosen.get("url") or "")


def generate_now_playing_block(
    sp: spotipy.Spotify, session: requests.Session | None = None
) -> tuple[list[str], dict[str, str]]:
    current = sp.current_user_playing_track()
    item = (current or {}).get("item") or {}
    playing = bool(current and current.get("is_playing") and item)
    images = (item.get("album") or {}).get("images") or []
    # Use the large cover for the full-width artwork background.
    image = (
        min(images, key=lambda image: abs((image.get("width") or 0) - 760))
        if images and playing
        else {}
    )
    cover_url = str(image.get("url") or "")
    cover = fetch_image_base64(cover_url, session=session, timeout=15)

    assets = {
        "now-playing.svg": render_now_playing(current, cover),
        "now-playing-mobile.svg": render_now_playing(current, cover, compact=True),
    }
    if not playing:
        return [picture("now-playing", "Not playing anything right now."), ""], assets
    artists = ", ".join(a.get("name", "Unknown") for a in item.get("artists", []))
    album = str((item.get("album") or {}).get("name", ""))
    label = f"{item.get('name', 'Unknown')} — {artists} — {album}"
    card = picture("now-playing", label)
    url = str((item.get("external_urls") or {}).get("spotify") or "")
    if urlsplit(url).scheme == "https" and urlsplit(url).netloc == "open.spotify.com":
        card = f'<a href="{escape(url, quote=True)}">\n{card}\n</a>'
    return [card, ""], assets


def generate_recently_played_block(
    sp: spotipy.Spotify, session: requests.Session | None = None
) -> tuple[list[str], dict[str, str]]:
    items = sp.current_user_recently_played(limit=RECENTLY_PLAYED_LIMIT).get(
        "items", []
    )
    covers = [
        fetch_image_base64(
            pick_image_url(
                ((entry.get("track") or {}).get("album") or {}).get("images") or []
            ),
            session=session,
        )
        for entry in items
    ]
    assets = {
        "recently-played.svg": render_recently_played(items, covers, compact=False),
        "recently-played-mobile.svg": render_recently_played(
            items, covers, compact=True
        ),
    }
    alt = "Recently played tracks on Spotify: " + ", ".join(
        str((e.get("track") or {}).get("name") or "Unknown") for e in items[:5]
    )
    card = picture("recently-played", alt)
    user: dict[str, Any] = {}
    try:
        user = sp.current_user() or {}
    except (SpotifyException, requests.RequestException):
        pass
    url = str((user.get("external_urls") or {}).get("spotify") or "")
    if urlsplit(url).scheme == "https" and urlsplit(url).netloc == "open.spotify.com":
        card = f'<a href="{escape(url, quote=True)}">\n{card}\n</a>'
    return ["### Recently played", "", card, ""], assets


def generate_top_block(
    sp: spotipy.Spotify, session: requests.Session | None = None
) -> tuple[list[str], dict[str, str]]:
    artists = sp.current_user_top_artists(limit=TOP_LIMIT, time_range="short_term").get(
        "items", []
    )
    tracks = sp.current_user_top_tracks(limit=TOP_LIMIT, time_range="short_term").get(
        "items", []
    )
    t_covers = [
        fetch_image_base64(
            pick_image_url((trk.get("album") or {}).get("images") or []),
            session=session,
        )
        for trk in tracks
    ]
    a_covers = [
        fetch_image_base64(
            pick_image_url(art.get("images") or []),
            session=session,
        )
        for art in artists
    ]
    assets = {
        "on-repeat.svg": render_on_repeat(
            tracks, artists, t_covers, a_covers, compact=False
        ),
        "on-repeat-mobile.svg": render_on_repeat(
            tracks, artists, t_covers, a_covers, compact=True
        ),
    }
    alt = "Top tracks on repeat on Spotify: " + ", ".join(
        str(t.get("name") or "Unknown") for t in tracks[:5]
    )
    card = picture("on-repeat", alt)
    user: dict[str, Any] = {}
    try:
        user = sp.current_user() or {}
    except (SpotifyException, requests.RequestException):
        pass
    url = str((user.get("external_urls") or {}).get("spotify") or "")
    if urlsplit(url).scheme == "https" and urlsplit(url).netloc == "open.spotify.com":
        card = f'<a href="{escape(url, quote=True)}">\n{card}\n</a>'
    return ["### On repeat", "", "Short-term listening.", "", card, ""], assets


def generate_snapshot() -> tuple[str, dict[str, str]]:
    """Fetch a complete snapshot; failures leave the previous README untouched."""
    sp = get_spotify_client()
    session = getattr(sp, "requests_session", None)
    parts, assets = generate_now_playing_block(sp, session=session)
    rp_parts, rp_assets = generate_recently_played_block(sp, session=session)
    top_parts, top_assets = generate_top_block(sp, session=session)
    parts.extend(rp_parts)
    assets.update(rp_assets)
    parts.extend(top_parts)
    assets.update(top_assets)
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    parts.append(f"<sub>{now}</sub>")
    assets["technologies.svg"] = render_technologies()
    assets["technologies-mobile.svg"] = render_technologies(compact=True)
    return "\n".join(parts), assets


def update_readme(path: Path = README_PATH) -> None:
    """Replace only the single marked block, atomically and without regex expansion."""
    content = path.read_text(encoding="utf-8")
    if content.count(START) != 1 or content.count(END) != 1:
        raise ValueError("README must contain exactly one pair of Spotify markers")
    before, rest = content.split(START)
    if END not in rest:
        raise ValueError("Spotify markers are out of order")
    _, after = rest.split(END)
    snippet, assets = generate_snapshot()
    updated = before + START + "\n" + snippet + "\n" + END + after
    for name, svg in assets.items():
        asset_path = path.parent / "assets" / "generated" / name
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(asset_path, svg)
    write_atomic(path, updated)
    logger.info("README and SVG cards updated successfully")


def write_atomic(path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as file:
            temporary = Path(file.name)
            file.write(content)
        temporary.chmod(path.stat().st_mode if path.exists() else 0o644)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


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
