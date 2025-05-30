#!/usr/bin/env python3
"""
Script to obtain Spotify OAuth refresh token.
Requires:
  pip install flask requests
Ensure SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET are set as
environment variables.
"""

import os
import webbrowser
from typing import Tuple, Union

import requests  # type: ignore
from dotenv import load_dotenv
from flask import Flask, request

load_dotenv()

app = Flask(__name__)
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = "http://127.0.0.1:8888/callback"
TOKEN_URL = "https://accounts.spotify.com/api/token"

if not CLIENT_ID or not CLIENT_SECRET:
    print(
        "Error: Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables."  # noqa: E501
    )
    exit(1)


@app.route("/callback")
def callback() -> Union[str, Tuple[str, int]]:
    code = request.args.get("code")
    if not code:
        return "Error: Missing code parameter.", 400
    # Exchange code for tokens
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    response = requests.post(TOKEN_URL, data=payload)
    if response.status_code != 200:
        return f"Token request failed: {response.text}", 400
    data = response.json()
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        return f"No refresh_token in response: {data}", 400
    # Show and print the refresh token
    result = f"Your Spotify Refresh Token is:\n{refresh_token}\n"
    print(result)
    shutdown = request.environ.get("werkzeug.server.shutdown")
    if shutdown:
        shutdown()
    return f"<html><body><h1>Success</h1><p>Copy your refresh token:</p><pre>{refresh_token}</pre></body></html>"  # noqa: E501


def main() -> None:
    # Open Spotify auth URL
    scopes = "user-read-currently-playing user-read-recently-played user-top-read"  # noqa: E501
    auth_url = (
        "https://accounts.spotify.com/authorize"
        f"?client_id={CLIENT_ID}"
        "&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={scopes.replace(' ', '%20')}"
    )
    print("Opening browser for Spotify authorization...")
    webbrowser.open(auth_url)
    print("Waiting for callback and token exchange...")
    app.run(host="127.0.0.1", port=8888)


if __name__ == "__main__":
    main()
