# README / regeneration

The personal paragraphs in `README.md` are handwritten. Edit them directly;
there is no template or AI rewrite step. The updater replaces only the content
between `<!-- SPOTIFY-START -->` and `<!-- SPOTIFY-END -->`. Keep exactly one
pair of those comments, in that order.

The banner, animated logo and poster collage live in `assets/`. The layout uses
Markdown and HTML tables, without custom CSS. Metrics are inside a collapsible
section; GitHub totals, contribution history and languages use
[GitHub Profile Summary Cards](https://github.com/vn7n24fzkq/github-profile-summary-cards),
and streaks use [Streak Stats](https://streak-stats.demolab.com/).
These images still depend on public external services. Languages are ranked by
repository count, not coding time. WakaTime is linked directly because its old
card provider is unavailable.

## 01 / Local setup

Use Python 3.12 or newer. From the repository directory:

```bash
uv sync --locked
cp .env.example .env
```

Copy `.env.example` only on first setup; keep an existing `.env`.
Fill in `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` from your Spotify app.
The included token helper uses `http://127.0.0.1:8888/callback`; configure that
exact redirect URI in the app and leave the `.env` redirect at its default.

```bash
uv run generate_refresh_token.py
```

Authorize in the browser, copy the returned token into
`SPOTIFY_REFRESH_TOKEN` in `.env`, then stop the helper with Ctrl+C.
Credentials and tokens belong in `.env`, never in the README or commits.

## 02 / Regenerate

```bash
uv run spotify_update.py
git diff -- README.md
```

The script locates the README beside itself, validates the markers before
calling Spotify, fetches the full snapshot, and replaces the file atomically.
If a request fails, the existing snapshot is preserved and the command fails.
Track and artist names are escaped before insertion into HTML.

Playback includes the album cover supplied by Spotify when available, with a
text-only fallback when no cover exists. It is a snapshot at the displayed UTC
timestamp, not a live player.
Recently played tracks use absolute UTC times so they stay meaningful between
refreshes. Artist and track rankings use Spotify's `short_term` range.

## 03 / GitHub Actions

Add these repository secrets under **Settings → Secrets and variables → Actions**:

- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `SPOTIFY_REFRESH_TOKEN`

The **Update README with Spotify Data** workflow requests write access to
repository contents. Repository rules must allow its bot to push to the default
branch. It runs on a 15-minute schedule, can be started with **Run workflow**,
and runs when the updater, requirements or its workflow change on `main`.
Scheduled execution may be delayed; the timestamp shows the last successful refresh.

Only `README.md` is staged by the bot. Your personal copy and layout stay
outside the generated markers. A failed run keeps the previous committed snapshot;
check the Actions log and credentials before retrying.

## 04 / Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `SPOTIFY_CLIENT_ID` | Required | Spotify app ID |
| `SPOTIFY_CLIENT_SECRET` | Required | Spotify app secret |
| `SPOTIFY_REFRESH_TOKEN` | Required | Token from the one-time helper |
| `SPOTIFY_REDIRECT_URI` | `http://127.0.0.1:8888/callback` | Updater OAuth redirect; the included helper uses this fixed default |
| `SPOTIFY_RECENTLY_PLAYED_LIMIT` | `5` | Recent tracks to display |
| `SPOTIFY_TOP_LIMIT` | `5` | Entries in each ranking |
| `SPOTIFY_PROGRESS_BAR_WIDTH` | `20` | Playback bar width in characters |
| `SPOTIFY_AUTH_RETRIES` | `4` | Token refresh attempts |
| `SPOTIFY_AUTH_RETRY_BASE_DELAY` | `5` | Initial retry delay in seconds, doubled between attempts |

## 05 / Verify changes

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest -q
```

Tests run without contacting Spotify. They cover playback formatting, escaped
metadata, missing or duplicate markers, literal backslashes, failed requests,
and preservation of text outside the generated section.
