#!/usr/bin/env python3
"""
Update the README Spotify section with current, recent, and top tracks/artists.
"""
import os
import re
import sys
from datetime import datetime
from typing import List

import requests  # type: ignore
import spotipy
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter  # type: ignore
from spotipy.oauth2 import SpotifyOAuth
from urllib3.util.retry import Retry

load_dotenv()

# Spotify API settings
SCOPE = "user-read-currently-playing user-read-recently-played user-top-read"
REDIRECT_URI = os.getenv(
    "SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"
)  # noqa: E501
RECENTLY_PLAYED_LIMIT = int(os.getenv("SPOTIFY_RECENTLY_PLAYED_LIMIT", "5"))
TOP_LIMIT = int(os.getenv("SPOTIFY_TOP_LIMIT", "5"))
PROGRESS_BAR_WIDTH = int(os.getenv("SPOTIFY_PROGRESS_BAR_WIDTH", "20"))


def get_spotify_client() -> spotipy.Spotify:
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    refresh_token = os.getenv("SPOTIFY_REFRESH_TOKEN")
    if not all([client_id, client_secret, refresh_token]):
        print(
            "Error: Missing Spotify credentials (CLIENT_ID, CLIENT_SECRET, or REFRESH_TOKEN)",  # noqa: E501
            file=sys.stderr,
        )
        sys.exit(1)
    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        show_dialog=False,
    )
    auth_manager.refresh_token = refresh_token
    token_info = auth_manager.refresh_access_token(refresh_token)
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return spotipy.Spotify(
        auth=token_info["access_token"], requests_session=session
    )  # noqa: E501


def format_duration(ms: int) -> str:
    minutes = ms // 60000
    seconds = (ms % 60000) // 1000
    return f"{minutes}:{seconds:02d}"


def create_progress_bar(
    progress_ms: int, duration_ms: int, width: int = PROGRESS_BAR_WIDTH
) -> str:
    if not progress_ms or not duration_ms:
        return "▬" * width
    progress = min(progress_ms / duration_ms, 1.0)
    filled = int(progress * width)
    return "▬" * filled + "🔘" + "▬" * (width - filled - 1)


def generate_now_playing_block(sp: spotipy.Spotify) -> List[str]:
    block: List[str] = ["### 🟢 Now Playing"]
    try:
        current = sp.current_user_playing_track()
        if not current or not current.get("is_playing"):
            block.append("Not playing anything right now.")
            return block
        item = current.get("item", {})
        name = item.get("name", "")
        artists = ", ".join(a["name"] for a in item.get("artists", []))
        url = item.get("external_urls", {}).get("spotify", "")
        album = item.get("album", {}).get("name", "")
        cover_url = item.get("album", {}).get("images", [{}])[0].get("url", "")
        duration_ms = item.get("duration_ms", 0)
        progress_ms = current.get("progress_ms", 0)
        block.extend(
            [
                '<p align="center">',
                f'<img src="{cover_url}" alt="Cover Art" width="120"/>',
                "</p>",
                "",
                f"**[{name}]({url})**",
                f"by {artists}",
                f"Album: {album}",
                "",
                f"{format_duration(progress_ms)} {create_progress_bar(progress_ms, duration_ms)} {format_duration(duration_ms)}",  # noqa: E501
            ]
        )
    except Exception:
        block.append("Error fetching now playing track.")
    return block


def generate_recently_played_block(sp: spotipy.Spotify) -> List[str]:
    block: List[str] = ["### 📜 Recently Played"]
    try:
        results = sp.current_user_recently_played(limit=RECENTLY_PLAYED_LIMIT)
        items = results.get("items", [])
        if not items:
            block.append("No recently played tracks.")
            return block
        for entry in items:
            track = entry.get("track", {})
            name = track.get("name", "")
            artists = ", ".join(a["name"] for a in track.get("artists", []))
            url = track.get("external_urls", {}).get("spotify", "")
            album = track.get("album", {}).get("name", "")
            block.append(f"- **[{name}]({url})** by {artists} ({album})")
    except Exception:
        block.append("Error fetching recently played tracks.")
    return block


def generate_top_artists_block(sp: spotipy.Spotify) -> List[str]:
    block: List[str] = ["### 🌟 Top Artists (Short Term)"]
    try:
        results = sp.current_user_top_artists(
            limit=TOP_LIMIT, time_range="short_term"
        )  # noqa: E501
        items = results.get("items", [])
        if not items:
            block.append("No top artists data available.")
            return block
        for i, artist in enumerate(items, start=1):
            name = artist.get("name", "")
            url = artist.get("external_urls", {}).get("spotify", "")
            block.append(f"{i}. [{name}]({url})")
    except Exception:
        block.append("Error fetching top artists.")
    return block


def generate_top_tracks_block(sp: spotipy.Spotify) -> List[str]:
    block: List[str] = ["### 🎶 Top Tracks (Short Term)"]
    try:
        results = sp.current_user_top_tracks(
            limit=TOP_LIMIT, time_range="short_term"
        )  # noqa: E501
        items = results.get("items", [])
        if not items:
            block.append("No top tracks data available.")
            return block
        for i, track in enumerate(items, start=1):
            name = track.get("name", "")
            url = track.get("external_urls", {}).get("spotify", "")
            block.append(f"{i}. [{name}]({url})")
    except Exception:
        block.append("Error fetching top tracks.")
    return block


def generate_markdown() -> str:
    sp = get_spotify_client()
    md: List[str] = []
    md.extend(generate_now_playing_block(sp))
    md.append("")
    md.extend(generate_recently_played_block(sp))
    md.append("")
    md.extend(generate_top_artists_block(sp))
    md.append("")
    md.extend(generate_top_tracks_block(sp))
    md.append("")
    md.append(
        f"_Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%SZ')} UTC_"  # noqa: E501
    )  # noqa: E501
    return "\n".join(md)


def update_readme() -> None:
    snippet = generate_markdown()
    try:
        path = os.path.join(os.getcwd(), "README.md")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        pattern = re.compile(
            r"<!-- SPOTIFY-START -->(.*?)<!-- SPOTIFY-END -->", re.DOTALL
        )
        new_section = (
            f"<!-- SPOTIFY-START -->\n{snippet}\n<!-- SPOTIFY-END -->"  # noqa: E501
        )
        updated = pattern.sub(new_section, content)
        with open(path, "w", encoding="utf-8") as f:
            f.write(updated)
    except Exception as e:
        print(f"Error updating README: {e}", file=sys.stderr)


if __name__ == "__main__":
    update_readme()
