#!/usr/bin/env python3
import os
import base64
import requests
import re
from datetime import datetime

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
CURRENTLY_PLAYING_URL = "https://api.spotify.com/v1/me/player/currently-playing"
RECENTLY_PLAYED_URL = "https://api.spotify.com/v1/me/player/recently-played?limit=5"

def get_access_token(client_id, client_secret, refresh_token):
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    response = requests.post(SPOTIFY_TOKEN_URL, data=payload, headers=headers)
    response.raise_for_status()
    return response.json().get("access_token")

def get_currently_playing(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(CURRENTLY_PLAYING_URL, headers=headers)
    if response.status_code != 200:
        return None
    data = response.json()
    if not data.get("is_playing"):
        return None
    item = data.get("item", {})
    artists = ", ".join([artist["name"] for artist in item.get("artists", [])])
    name = item.get("name")
    url = item.get("external_urls", {}).get("spotify")
    album = item.get("album", {}).get("name", "")
    images = item.get("album", {}).get("images", [])
    cover_url = images[0]["url"] if images else ""
    duration_ms = item.get("duration_ms", 0)
    progress_ms = data.get("progress_ms", 0)
    return {
        "name": name,
        "artists": artists,
        "album": album,
        "url": url,
        "cover_url": cover_url,
        "duration_ms": duration_ms,
        "progress_ms": progress_ms
    }

def get_recently_played(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(RECENTLY_PLAYED_URL, headers=headers)
    response.raise_for_status()
    items = response.json().get("items", [])
    tracks = []
    for entry in items:
        item = entry.get("track", {})
        artists = ", ".join([artist["name"] for artist in item.get("artists", [])])
        name = item.get("name")
        url = item.get("external_urls", {}).get("spotify")
        album = item.get("album", {}).get("name", "")
        images = item.get("album", {}).get("images", [])
        cover_url = images[-1]["url"] if images else ""
        tracks.append({
            "name": name,
            "artists": artists,
            "album": album,
            "url": url,
            "cover_url": cover_url
        })
    return tracks

def format_duration(ms):
    minutes = ms // 60000
    seconds = (ms % 60000) // 1000
    return f"{minutes}:{seconds:02d}"

def create_progress_bar(progress_ms, duration_ms, width=20):
    if not progress_ms or not duration_ms:
        return "▬" * width
    progress = min(progress_ms / duration_ms, 1.0)
    filled = int(progress * width)
    return "▬" * filled + "🔘" + "▬" * (width - filled - 1)

def generate_markdown():
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    refresh_token = os.getenv("SPOTIFY_REFRESH_TOKEN")
    if not all([client_id, client_secret, refresh_token]):
        return "**Spotify credentials not set**"
    try:
        token = get_access_token(client_id, client_secret, refresh_token)
    except Exception as e:
        return f"**Error refreshing Spotify token**: {e}"
    now = get_currently_playing(token)
    recent = []
    try:
        recent = get_recently_played(token)
    except Exception:
        recent = []
    md = []
    md.append("### 🟢 Now Playing")
    if now:
        md.append("<p align=\"center\">")
        md.append(f"<img src=\"{now['cover_url']}\" alt=\"Cover Art\" width=\"120\"/>")
        md.append("</p>")
        md.append("")
        md.append(f"[{now['name']}]({now['url']})")
        md.append(f"by {now['artists']}")
        md.append(f"Album: {now['album']}")
        md.append("")
        md.append(f"{format_duration(now['progress_ms'])} {create_progress_bar(now['progress_ms'], now['duration_ms'])} {format_duration(now['duration_ms'])}")
    else:
        md.append("Not playing anything right now.")
    md.append("")
    md.append("### 📜 Recently Played")
    if recent:
        for track in recent:
            md.append(f"<img src=\"{track['cover_url']}\" alt=\"Cover Art\" width=\"64\" style=\"vertical-align:middle;margin-right:10px;\"/>")
            md.append(f"[{track['name']}]({track['url']})")
            md.append(f"by {track['artists']}")
            md.append(f"Album: {track['album']}")
            md.append("")
    else:
        md.append("No recently played tracks.")
    md.append("")
    md.append(f"_Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%SZ')} UTC_")
    return "\n".join(md)

def update_readme():
    snippet = generate_markdown()
    print("DEBUG: Spotify snippet\n" + snippet)
    try:
        with open("README.md", "r", encoding="utf-8") as f:
            content = f.read()
        pattern = re.compile(r"<!-- SPOTIFY-START -->(.*?)<!-- SPOTIFY-END -->", re.DOTALL)
        new_section = f"<!-- SPOTIFY-START -->\n{snippet}\n<!-- SPOTIFY-END -->"
        updated = pattern.sub(new_section, content)
        with open("README.md", "w", encoding="utf-8") as f:
            f.write(updated)
    except Exception as e:
        print(f"Error updating README: {e}")

if __name__ == "__main__":
    update_readme()