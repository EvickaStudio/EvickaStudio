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
    return f"[{name} by {artists}]({url})"

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
        tracks.append(f"- [{name} by {artists}]({url})")
    return tracks

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
    now_playing = get_currently_playing(token)
    recently_played = []
    try:
        recently_played = get_recently_played(token)
    except Exception:
        recently_played = []
    md = []
    md.append("### 🟢 Now Playing")
    if now_playing:
        md.append(f"- {now_playing}")
    else:
        md.append("- Not playing anything right now.")
    md.append("")
    md.append("### 📜 Recently Played")
    if recently_played:
        md.extend(recently_played)
    else:
        md.append("- No recently played tracks.")
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