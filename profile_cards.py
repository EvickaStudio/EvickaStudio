"""Self-contained SVG panels for the profile; no browser or graphics dependency."""

from datetime import UTC, datetime
from html import escape
from textwrap import wrap
from typing import Any

from spotify_fonts import SPOTIFY_FONT_FACES, SPOTIFY_FONT_STACK

TECHNOLOGIES = (
    ("Programming", "Python · Java · Rust"),
    ("Design Tools", "Figma · Photoshop · Illustrator · Gimp"),
    ("Databases", "SQL (MySQL, SQLite, MariaDB)"),
    ("3D Tools", "Blender · ZBrush"),
    ("IDEs", "JetBrains (IntelliJ) · VS Code · Zed"),
    ("Other", "Git · Docker · Kubernetes"),
    ("Operating Systems", "Linux (EndeavourOS, CachyOS, Debian, Ubuntu) · Windows"),
)


def text(x: int, y: int, value: str, size: int = 18, css: str = "") -> str:
    return (
        f'<text x="{x}" y="{y}" font-size="{size}" class="{css}">{escape(value)}</text>'
    )


def format_played_at(played_at_str: str) -> str:
    if not played_at_str:
        return ""
    try:
        dt = datetime.fromisoformat(played_at_str).astimezone(UTC)
        return dt.strftime("%d %b · %H:%M")
    except (ValueError, TypeError):
        return ""


def panel(width: int, height: int, title: str, body: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">
<title id="title">{escape(title)}</title>
<style>
{SPOTIFY_FONT_FACES}
text {{ font-family: {SPOTIFY_FONT_STACK}; fill: #292329; }}
.label {{ fill: #b3b3b3; font-weight: 400; }}
.muted {{ fill: #b3b3b3; font-weight: 400; }}
@media (prefers-color-scheme: dark) {{
  text {{ fill: #ffffff; }}
  .label {{ fill: #b3b3b3; }}
  .muted {{ fill: #b3b3b3; }}
}}
.title {{ font-weight: 700; }}
</style>
{body}
</svg>
"""


def render_technologies(compact: bool = False) -> str:
    width = 400 if compact else 760
    body = []
    for index, (label, value) in enumerate(TECHNOLOGIES):
        x = 24 if compact else 28 + (index % 2) * 370
        if index == 6:
            x = 24 if compact else 28
        y = 34 + (index if compact else index // 2) * 90
        body.append(text(x, y, label, 14, "label"))
        lines = wrap(value, width=34 if compact else (70 if index == 6 else 42))
        for line_index, line in enumerate(lines):
            body.append(text(x, y + 29 + line_index * 24, line))
    return panel(width, 654 if compact else 364, "Technologies", "\n".join(body))


def clipped_text(
    x: int, y: int, value: str, width: int, size: int = 14, css: str = ""
) -> str:
    """Fade long metadata inside its own viewport, independent of font metrics."""
    height = size + 8
    return (
        f'<svg x="{x}" y="{y - size}" width="{width}" height="{height}" overflow="hidden">'
        f'<defs><mask id="line-{x}-{y}" maskUnits="userSpaceOnUse" '
        f'x="0" y="0" width="{width}" height="{height}">'
        f'<rect width="{width}" height="{height}" fill="url(#text-fade)"/>'
        f'</mask></defs><g mask="url(#line-{x}-{y})">'
        + text(0, size, value, size, css)
        + "</g></svg>"
    )


def artwork(x: int, y: int, size: int, cover: str, rounded: bool = False) -> str:
    radius = size // 2 if rounded else 6
    clip = f"art-{x}-{y}"
    body = (
        f'<defs><clipPath id="{clip}"><rect x="{x}" y="{y}" width="{size}" '
        f'height="{size}" rx="{radius}"/></clipPath></defs>'
        f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="{radius}" fill="#252a30"/>'
    )
    if cover:
        body += (
            f'<image x="{x}" y="{y}" width="{size}" height="{size}" '
            f'preserveAspectRatio="xMidYMid slice" clip-path="url(#{clip})" '
            f'xlink:href="{escape(cover, quote=True)}"/>'
        )
    else:
        body += text(x + size // 2, y + size // 2 + 5, "♪", 18, "muted center")
    return body


def render_spotify(
    current: dict[str, Any] | None,
    recent: list[dict[str, Any]],
    tracks: list[dict[str, Any]],
    artists: list[dict[str, Any]],
    cover: str = "",
    recent_covers: list[str] | None = None,
    track_covers: list[str] | None = None,
    artist_covers: list[str] | None = None,
    updated_at: str = "",
    compact: bool = False,
) -> str:
    width = 400 if compact else 760
    pad = 24 if compact else 32
    hero_height = 300 if compact else 320
    recent, tracks, artists = recent[:5], tracks[:5], artists[:5]
    recent_height = 92 + max(1, len(recent)) * 72
    repeat_height = 92 + max(1, len(tracks)) * 72
    lists_height = (
        recent_height + repeat_height if compact else max(recent_height, repeat_height)
    )
    artists_y = hero_height + lists_height
    artists_height = 72 + len(artists) * 52 if compact else 204
    if not artists:
        artists_height = 112
    footer_y = artists_y + artists_height
    height = footer_y + 52
    col_width = width - pad * 2 if compact else (width - pad * 2 - 40) // 2

    current_item = (current or {}).get("item") or {}
    playing = bool((current or {}).get("is_playing") and current_item)
    item = current_item or ((recent[0].get("track") or {}) if recent else {})
    name = str(item.get("name") or "Nothing playing")
    performers = ", ".join(a.get("name", "Unknown") for a in item.get("artists", []))
    album = str((item.get("album") or {}).get("name") or "")
    status = "Now playing" if playing else "Paused" if current_item else "Last played"
    description = [f"Spotify. {status}: {name} — {performers} — {album}."]
    body = [
        """<style>
.spotify text { fill: #f4f5f7; }
.spotify .title { font-weight: 700; }
.spotify .muted { fill: #b1b5bd; }
.spotify .quiet { fill: #939ba7; }
.spotify .accent { fill: #1ed760; }
.spotify .end { text-anchor: end; font-variant-numeric: tabular-nums; }
.spotify .center { text-anchor: middle; }
.spotify .rule { stroke: #ffffff; stroke-opacity: .09; }
</style>""",
        f'<defs><clipPath id="spotify-card"><rect width="{width}" height="{height}" rx="20"/></clipPath>',
        (
            '<linearGradient id="hero-shade" x1="0" y1="0" x2="0" y2="1" gradientUnits="objectBoundingBox">'
            '<stop stop-color="#101317" stop-opacity=".15"/>'
            '<stop offset=".6" stop-color="#101317" stop-opacity=".35"/>'
            '<stop offset="1" stop-color="#101317"/></linearGradient>'
        ),
        (
            '<linearGradient id="text-fade"><stop offset=".88" stop-color="white"/>'
            '<stop offset="1" stop-color="black"/></linearGradient></defs>'
        ),
        '<g class="spotify" clip-path="url(#spotify-card)">',
        f'<rect width="{width}" height="{height}" fill="#101317"/>',
        '<g id="now-playing">',
    ]
    if cover:
        body += [
            (
                f'<image width="{width}" height="{hero_height}" preserveAspectRatio="xMidYMid slice" '
                f'xlink:href="{escape(cover, quote=True)}"/>'
            ),
            f'<rect width="{width}" height="{hero_height}" fill="#000000" opacity=".6"/>',
        ]
    body.append(
        f'<rect width="{width}" height="{hero_height}" fill="url(#hero-shade)"/>'
    )
    body.append(
        f'<rect y="{hero_height - 1}" width="{width}" height="2" fill="#101317"/>'
    )
    # ponytail: hero wrapping assumes ordinary titles; clip wide glyphs and keep full metadata in title/alt.
    lines = wrap(name, width=23 if compact else 38, max_lines=2, placeholder="…")
    title_y = 105 if compact else 121
    line_height = 34 if compact else 40
    for index, line in enumerate(lines):
        body.append(
            clipped_text(
                pad,
                title_y + index * line_height,
                line,
                width - pad * 2,
                28 if compact else 36,
                "title",
            )
        )
    artist_y = title_y + (len(lines) - 1) * line_height + 36
    body += [
        clipped_text(
            pad,
            artist_y,
            (performers or "Unknown artist")
            if item
            else "Not playing anything right now.",
            width - pad * 2,
            17 if compact else 20,
        ),
        clipped_text(pad, artist_y + 26, album, width - pad * 2, 13, "muted"),
    ]
    duration = max(0, int(item.get("duration_ms") or 0))
    duration_label = (
        f"{duration // 60000}:{duration // 1000 % 60:02d}" if duration else ""
    )
    if current_item:
        progress = max(0, min(int((current or {}).get("progress_ms") or 0), duration))
        bar_width = width - pad * 2
        fraction = progress / duration if duration else 0
        body += [
            f'<rect id="playback-rail" x="{pad}" y="{hero_height - 50}" width="{bar_width}" height="3" rx="1.5" fill="#ffffff" fill-opacity=".2"/>',
            f'<rect id="playback-progress" x="{pad}" y="{hero_height - 50}" width="{bar_width * fraction:.2f}" height="3" rx="1.5" fill="#ffffff"/>',
            text(
                pad,
                hero_height - 25,
                f"{progress // 60000}:{progress // 1000 % 60:02d}",
                11,
                "muted",
            ),
        ]
        if not playing:
            body.append(
                text(width // 2, hero_height - 25, "Paused", 11, "muted center")
            )
    elif recent:
        played = format_played_at(str(recent[0].get("played_at") or ""))
        body.append(
            text(
                pad,
                hero_height - 25,
                f"Last listened · {played} UTC" if played else "Last listened",
                11,
                "muted",
            )
        )
    body += [
        text(width - pad, hero_height - 25, duration_label, 11, "muted end"),
        "</g>",
    ]

    for index, (section, heading, subtitle, entries, covers) in enumerate(
        (
            (
                "recently-played",
                "Recently played",
                "Latest listens · UTC",
                recent,
                recent_covers or [],
            ),
            (
                "on-repeat",
                "On repeat",
                "Top tracks · short term",
                tracks,
                track_covers or [],
            ),
        )
    ):
        x = pad if compact else pad + index * (col_width + 40)
        y = hero_height + (recent_height if compact and index else 0)
        body += [
            f'<g id="{section}">',
            text(x, y + 34, heading, 20, "title"),
            text(x, y + 55, subtitle, 11, "quiet"),
        ]
        if not entries:
            body.append(
                text(
                    x,
                    y + 105,
                    "No recently played tracks."
                    if index == 0
                    else "No top tracks yet.",
                    13,
                    "muted",
                )
            )
        for rank, entry in enumerate(entries):
            track = (entry.get("track") or {}) if index == 0 else entry
            track_name = str(track.get("name") or "Unknown")
            artist = ", ".join(
                a.get("name", "Unknown") for a in track.get("artists", [])
            )
            track_album = str((track.get("album") or {}).get("name") or "")
            ms = max(0, int(track.get("duration_ms") or 0))
            duration_text = f"{ms // 60000}:{ms // 1000 % 60:02d}" if ms else ""
            played = (
                format_played_at(str(entry.get("played_at") or ""))
                if index == 0
                else ""
            )
            row_y = y + 78 + rank * 72
            art_x = x + (22 if index else 0)
            tx = art_x + 54
            available = x + col_width - tx
            full_title = f"{track_name} — {artist} — {track_album}" + (
                f" · {played} UTC" if played else ""
            )
            description.append(f"{heading} {rank + 1}: {full_title}.")
            body.append(f"<g><title>{escape(full_title)}</title>")
            if index:
                body.append(text(x, row_y + 27, f"{rank + 1:02d}", 10, "quiet"))
            body += [
                artwork(
                    art_x, row_y + 4, 42, covers[rank] if rank < len(covers) else ""
                ),
                clipped_text(tx, row_y + 16, track_name, available - 34, 14, "title"),
                text(x + col_width, row_y + 16, duration_text, 11, "quiet end"),
                clipped_text(tx, row_y + 34, artist, available, 12, "muted"),
                clipped_text(
                    tx,
                    row_y + 51,
                    track_album,
                    available - (88 if played else 0),
                    10,
                    "quiet",
                ),
                text(x + col_width, row_y + 51, played, 10, "quiet end"),
                "</g>",
            ]
        body.append("</g>")

    body += [
        f'<path d="M{pad} {artists_y}H{width - pad}" class="rule"/>',
        '<g id="top-artists">',
        text(pad, artists_y + 35, "Top artists", 20, "title"),
        text(width - pad, artists_y + 35, "Short term", 11, "quiet end"),
    ]
    if not artists:
        body.append(text(pad, artists_y + 79, "No top artists yet.", 13, "muted"))
    for index, artist in enumerate(artists):
        artist_name = str(artist.get("name") or "Unknown")
        genres = artist.get("genres") or []
        genre = str(genres[0]).title() if genres else "Artist"
        description.append(
            f"Top artist {index + 1}: {artist_name} — {', '.join(genres) or 'Artist'}."
        )
        artist_cover = (
            (artist_covers or [])[index] if index < len(artist_covers or []) else ""
        )
        body.append(
            f"<g><title>{escape(artist_name + ' — ' + (', '.join(genres) or 'Artist'))}</title>"
        )
        if compact:
            row_y = artists_y + 58 + index * 52
            body += [
                text(pad, row_y + 24, f"{index + 1:02d}", 11, "quiet"),
                artwork(pad + 28, row_y, 38, artist_cover, rounded=True),
                clipped_text(
                    pad + 80, row_y + 15, artist_name, width - pad * 2 - 80, 14, "title"
                ),
                clipped_text(
                    pad + 80, row_y + 33, genre, width - pad * 2 - 80, 11, "muted"
                ),
            ]
        else:
            cell_width = (width - pad * 2) // 5
            x = pad + index * cell_width
            center = x + cell_width // 2
            body += [
                artwork(center - 36, artists_y + 59, 72, artist_cover, rounded=True),
                f'<circle cx="{center + 25}" cy="{artists_y + 123}" r="11" fill="#20292a" stroke="#101317" stroke-width="3"/>',
                text(
                    center + 25,
                    artists_y + 126,
                    f"{index + 1:02d}",
                    9,
                    "accent center title",
                ),
                clipped_text(
                    x + 8, artists_y + 155, artist_name, cell_width - 16, 13, "title"
                ),
                clipped_text(
                    x + 8, artists_y + 175, genre, cell_width - 16, 11, "muted"
                ),
            ]
        body.append("</g>")
    body += [
        "</g>",
        f'<path d="M{pad} {footer_y}H{width - pad}" class="rule"/>',
        text(
            pad,
            footer_y + 30,
            f"Updated {updated_at}" if updated_at else "Spotify listening snapshot",
            10,
            "quiet",
        ),
        text(width - pad, footer_y + 30, "Open Spotify ↗", 10, "muted end"),
        "</g>",
        f'<rect x=".5" y=".5" width="{width - 1}" height="{height - 1}" rx="20" fill="none" stroke="#ffffff" stroke-opacity=".1"/>',
    ]
    return panel(width, height, " ".join(description), "\n".join(body))


def picture(name: str, alt: str) -> str:
    return (
        "<picture>\n"
        f'<source media="(max-width: 600px)" srcset="assets/generated/{name}-mobile.svg" />\n'
        f'<img src="assets/generated/{name}.svg" alt="{escape(alt, quote=True)}" width="100%" />\n'
        "</picture>"
    )


if __name__ == "__main__":
    from pathlib import Path

    output = Path(__file__).resolve().parent / "assets" / "generated"
    output.mkdir(parents=True, exist_ok=True)
    for name, compact in (
        ("technologies.svg", False),
        ("technologies-mobile.svg", True),
    ):
        (output / name).write_text(render_technologies(compact), encoding="utf-8")
