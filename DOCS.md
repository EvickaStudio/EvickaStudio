# Evika Studio

## ⚙️ Setup

To configure and update this README locally, follow these steps:

1. Create a `.env` file in the root directory based on the [`.env.example`](.env.example) file:

   ```bash
   cp .env.example .env
   # then fill in your Spotify credentials and optional settings
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. (One-time) Obtain your Spotify refresh token:

   ```bash
   python3 generate_refresh_token.py
   ```

4. Generate and insert the Spotify section:

   ```bash
   python3 spotify_update.py
   ```

### Configuration

| Environment Variable               | Description                                              | Default                                         |
|------------------------------------|----------------------------------------------------------|-------------------------------------------------|
| `SPOTIFY_CLIENT_ID`                | Your Spotify application Client ID                       | n/a                                             |
| `SPOTIFY_CLIENT_SECRET`            | Your Spotify application Client Secret                   | n/a                                             |
| `SPOTIFY_REFRESH_TOKEN`            | OAuth2 refresh token for Spotify API                     | n/a                                             |
| `SPOTIFY_REDIRECT_URI`             | Redirect URI for Spotify OAuth flow                      | <http://127.0.0.1:8888/callback>                  |
| `SPOTIFY_RECENTLY_PLAYED_LIMIT`    | Number of tracks to display in "Recently Played"        | 5                                               |
| `SPOTIFY_TOP_LIMIT`                | Number of items to display in "Top Artists/Tracks"     | 5                                               |
| `SPOTIFY_PROGRESS_BAR_WIDTH`       | Width of the progress bar                                | 20                                              |

---

## 🎧 Spotify ![Spotify](https://img.shields.io/badge/Now_Playing-Spotify-green?logo=spotify&style=flat-square)
