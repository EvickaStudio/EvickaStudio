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
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")  # noqa: E501
RECENTLY_PLAYED_LIMIT = int(os.getenv("SPOTIFY_RECENTLY_PLAYED_LIMIT", "5"))
TOP_LIMIT = int(os.getenv("SPOTIFY_TOP_LIMIT", "5"))
PROGRESS_BAR_WIDTH = int(os.getenv("SPOTIFY_PROGRESS_BAR_WIDTH", "300"))


def get_spotify_client() -> spotipy.Spotify:
    """
    Initialize and return an authenticated Spotify client.

    Returns:
        spotipy.Spotify: Authenticated Spotify client instance.

    Raises:
        SystemExit: If required credentials are missing.
    """
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
    return spotipy.Spotify(auth=token_info["access_token"], requests_session=session)  # noqa: E501


def format_duration(ms: int) -> str:
    """
    Format milliseconds into MM:SS format.

    Args:
        ms (int): Duration in milliseconds.

    Returns:
        str: Formatted duration string (MM:SS).
    """
    minutes = ms // 60000
    seconds = (ms % 60000) // 1000
    return f"{minutes}:{seconds:02d}"


def create_progress_svg(
    progress_ms: int, duration_ms: int, width: int = PROGRESS_BAR_WIDTH
) -> str:
    """
    Create an SVG progress bar with current progress.

    Args:
        progress_ms (int): Current progress in milliseconds.
        duration_ms (int): Total duration in milliseconds.
        width (int): Width of the progress bar in pixels.

    Returns:
        str: SVG markup for the progress bar.
    """
    if not progress_ms or not duration_ms:
        progress_percent = 0
    else:
        progress_percent = min(progress_ms / duration_ms, 1.0)

    progress_width = int(progress_percent * width)
    current_time = format_duration(progress_ms)
    total_time = format_duration(duration_ms)

    return f'''
<p align="center">
<svg width="{width}" height="20" xmlns="http://www.w3.org/2000/svg">
    <rect width="{width}" height="4" fill="#282828" rx="2"/>
    <rect width="{progress_width}" height="4" fill="#1db954" rx="2"/>
    <circle cx="{progress_width}" cy="2" r="6" fill="#1db954"/>
</svg>
<br/>
<span style="font-size: 12px; color: #b3b3b3;">
    {current_time} • {total_time}
</span>
</p>
'''


def generate_now_playing_block(sp: spotipy.Spotify) -> List[str]:
    """
    Generate the "Now Playing" section with enhanced formatting.

    Args:
        sp (spotipy.Spotify): Authenticated Spotify client.

    Returns:
        List[str]: Markdown lines for the "Now Playing" section.
    """
    block: List[str] = ["", "", "### 🟢 Now Playing", ""]
    try:
        current = sp.current_user_playing_track()
        if not current or not current.get("is_playing"):
            block.extend(["🎵 Not playing anything right now.", "", ""])
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
                f'<img src="{cover_url}" alt="Cover Art" width="120" style="border-radius: 8px;"/>',  # noqa: E501
                "</p>",
                "",
                f"**🎵 [{name}]({url})**",
                f"*by* **{artists}**",
                f"*Album:* {album}",
                "",
                create_progress_svg(progress_ms, duration_ms),
                "",
            ]
        )
    except Exception:
        block.extend(["❌ Error fetching now playing track.", "", ""])
    return block


def generate_recently_played_block(sp: spotipy.Spotify) -> List[str]:
    """
    Generate the "Recently Played" section with enhanced formatting.

    Args:
        sp (spotipy.Spotify): Authenticated Spotify client.

    Returns:
        List[str]: Markdown lines for the "Recently Played" section.
    """
    block: List[str] = ["", "### 📜 Recently Played", ""]
    try:
        results = sp.current_user_recently_played(limit=RECENTLY_PLAYED_LIMIT)
        items = results.get("items", [])
        if not items:
            block.extend(["No recently played tracks.", "", ""])
            return block

        for entry in items:
            track = entry.get("track", {})
            name = track.get("name", "")
            artists = ", ".join(a["name"] for a in track.get("artists", []))
            url = track.get("external_urls", {}).get("spotify", "")
            album = track.get("album", {}).get("name", "")
            block.append(f"🎤 **[{name}]({url})** by **{artists}** *({album})*")

        block.extend(["", ""])
    except Exception:
        block.extend(["❌ Error fetching recently played tracks.", "", ""])
    return block


def generate_top_artists_block(sp: spotipy.Spotify) -> List[str]:
    """
    Generate the "Top Artists" section with enhanced formatting.

    Args:
        sp (spotipy.Spotify): Authenticated Spotify client.

    Returns:
        List[str]: Markdown lines for the "Top Artists" section.
    """
    block: List[str] = ["", "### 🌟 Top Artists *(Short Term)*", ""]
    try:
        results = sp.current_user_top_artists(limit=TOP_LIMIT, time_range="short_term")  # noqa: E501
        items = results.get("items", [])
        if not items:
            block.extend(["No top artists data available.", "", ""])
            return block

        medals = ["🥇", "🥈", "🥉", "🏅", "🏅"]
        for i, artist in enumerate(items):
            name = artist.get("name", "")
            url = artist.get("external_urls", {}).get("spotify", "")
            block.append(f"{medals[i]} [**{name}**]({url})")

        block.extend(["", ""])
    except Exception:
        block.extend(["❌ Error fetching top artists.", "", ""])
    return block


def generate_top_tracks_block(sp: spotipy.Spotify) -> List[str]:
    """
    Generate the "Top Tracks" section with enhanced formatting.

    Args:
        sp (spotipy.Spotify): Authenticated Spotify client.

    Returns:
        List[str]: Markdown lines for the "Top Tracks" section.
    """
    block: List[str] = ["", "### 🎶 Top Tracks *(Short Term)*", ""]
    try:
        results = sp.current_user_top_tracks(limit=TOP_LIMIT, time_range="short_term")  # noqa: E501
        items = results.get("items", [])
        if not items:
            block.extend(["No top tracks data available.", "", ""])
            return block

        medals = ["🥇", "🥈", "🥉", "🏅", "🏅"]
        for i, track in enumerate(items):
            name = track.get("name", "")
            url = track.get("external_urls", {}).get("spotify", "")
            block.append(f"{medals[i]} [**{name}**]({url})")

        block.extend(["", ""])
    except Exception:
        block.extend(["❌ Error fetching top tracks.", "", ""])
    return block


def generate_markdown() -> str:
    """
    Generate the complete Spotify section markdown.

    Returns:
        str: Complete markdown for the Spotify section.
    """
    sp = get_spotify_client()
    md: List[str] = []
    md.extend(generate_now_playing_block(sp))
    md.extend(generate_recently_played_block(sp))
    md.extend(generate_top_artists_block(sp))
    md.extend(generate_top_tracks_block(sp))
    md.append(
        f"🕐 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%SZ')} UTC"  # noqa: E501
    )
    return "\n".join(md)


def update_readme() -> None:
    """
    Update the Spotify section in the README.md file.

    Raises:
        Exception: If there's an error reading or writing the README file.
    """
    snippet = generate_markdown()
    try:
        path = os.path.join(os.getcwd(), "README.md")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        pattern = re.compile(
            r"<!-- SPOTIFY-START -->(.*?)<!-- SPOTIFY-END -->", re.DOTALL
        )
        new_section = f"<!-- SPOTIFY-START -->\n{snippet}\n<!-- SPOTIFY-END -->"  # noqa: E501
        updated = pattern.sub(new_section, content)
        with open(path, "w", encoding="utf-8") as f:
            f.write(updated)
    except Exception as e:
        print(f"Error updating README: {e}", file=sys.stderr)


if __name__ == "__main__":
    update_readme()
