"""Self-contained SVG panels for the profile; no browser or graphics dependency."""

from html import escape
from textwrap import shorten, wrap
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

CLOCK_ICON = (
    '<path d="M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13M0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8" fill="#b3b3b3"/>'
    '<path d="M8 3.25a.75.75 0 0 1 .75.75v3.25H11a.75.75 0 0 1 0 1.5H7.25V4A.75.75 0 0 1 8 3.25" fill="#b3b3b3"/>'
)


def text(x: int, y: int, value: str, size: int = 18, css: str = "") -> str:
    return (
        f'<text x="{x}" y="{y}" font-size="{size}" class="{css}">{escape(value)}</text>'
    )


def truncate_text(value: str, max_chars: int) -> str:
    value = value.strip()
    if len(value) <= max_chars:
        return value
    truncated = value[:max_chars].rstrip(". ,;-–—")
    return truncated + "…"


def format_played_at(played_at_str: str, compact: bool = False) -> str:
    if not played_at_str:
        return ""
    try:
        from datetime import UTC, datetime

        dt = datetime.fromisoformat(played_at_str).astimezone(UTC)
        now = datetime.now(UTC)
        diff = now - dt
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return "Just now"
        if seconds < 3600:
            m = max(1, seconds // 60)
            return f"{m} min ago" if not compact else f"{m}m ago"
        if seconds < 86400:
            h = max(1, seconds // 3600)
            return f"{h} hr ago" if not compact else f"{h}h ago"
        if seconds < 86400 * 7:
            d = max(1, seconds // 86400)
            return f"{d} day ago" if d == 1 else f"{d} days ago"
        return dt.strftime("%b %-d, %Y")
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


def render_now_playing(
    current: dict[str, Any] | None, cover: str = "", compact: bool = False
) -> str:
    width = 400 if compact else 760
    if not current or not current.get("is_playing") or not current.get("item"):
        return panel(
            width,
            120,
            "Not playing anything right now.",
            text(24, 67, "Not playing anything right now.", 20, "muted"),
        )
    item = current["item"]
    name = str(item.get("name") or "Unknown")
    artists = ", ".join(a.get("name", "Unknown") for a in item.get("artists", []))
    album = str((item.get("album") or {}).get("name", ""))
    duration = max(0, int(item.get("duration_ms") or 0))
    progress = max(0, min(int(current.get("progress_ms") or 0), duration))
    height = 280 if compact else 320
    body = [
        (
            f"<style>{SPOTIFY_FONT_FACES}\n"
            f"text {{ font-family: {SPOTIFY_FONT_STACK}; fill: #ffffff; }} "
            ".label { fill: #b3b3b3; font-weight: 700; letter-spacing: 1.5px; } "
            ".muted { fill: #b3b3b3; font-weight: 400; } "
            ".title { font-weight: 700; fill: #ffffff; } "
            ".rail { fill: #ffffff; fill-opacity: .25; } "
            ".accent { fill: #ffffff; } "
            ".card-border { stroke: rgba(255, 255, 255, 0.1); stroke-width: 1; fill: none; } "
            "@media (prefers-color-scheme: light) { .card-border { stroke: rgba(0, 0, 0, 0.15); } }</style>"
        ),
        f'<defs><clipPath id="card"><rect width="{width}" height="{height}" rx="16"/></clipPath></defs>',
        '<g clip-path="url(#card)">',
        f'<rect width="{width}" height="{height}" fill="#121212"/>',
    ]
    if cover:
        body.append(
            f'<image width="{width}" height="{height}" '
            f'preserveAspectRatio="xMidYMid slice" xlink:href="{escape(cover, quote=True)}"/>'
        )
        body.append(
            f'<rect width="{width}" height="{height}" fill="#000000" opacity=".6"/>'
        )
    body.append("</g>")
    body.append(
        f'<rect width="{width}" height="{height}" rx="16" class="card-border"/>'
    )
    body.append(text(32, 38, "SPOTIFY", 11, "label"))
    # ponytail: character wrapping assumes ordinary titles; full text remains in alt/title.
    lines = wrap(name, width=24 if compact else 40, max_lines=2, placeholder="…")
    title_y = 88 if compact else 111
    for index, line in enumerate(lines):
        body.append(
            text(32, title_y + index * 34, line, 24 if compact else 30, "title")
        )
    artist_y = title_y + len(lines) * 34 + 8
    body.append(
        text(
            32,
            artist_y,
            shorten(artists, width=30 if compact else 60, placeholder="…"),
            18 if compact else 21,
        )
    )
    body.append(
        text(
            32,
            artist_y + 28,
            shorten(album, width=38 if compact else 76, placeholder="…"),
            14,
            "muted",
        )
    )
    bar_width = width - 64
    bar_y = height - 54
    fraction = progress / duration if duration else 0
    body += [
        f'<rect x="32" y="{bar_y}" width="{bar_width}" height="4" rx="2" class="rail"/>',
        f'<rect x="32" y="{bar_y}" width="{bar_width * fraction:.2f}" height="4" rx="2" class="accent"/>',
        text(
            32,
            height - 26,
            f"{progress // 60000}:{progress // 1000 % 60:02d}",
            12,
            "muted",
        ),
        text(
            width - 62,
            height - 26,
            f"{duration // 60000}:{duration // 1000 % 60:02d}",
            12,
            "muted",
        ),
    ]
    return panel(width, height, f"{name} — {artists} — {album}", "\n".join(body))


def render_recently_played(
    items: list[dict[str, Any]],
    covers: list[str] | None = None,
    compact: bool = False,
) -> str:
    width = 400 if compact else 760
    covers = covers or []
    item_count = len(items[:5])

    if compact:
        row_h = 52
        header_y = 24
        start_y = 40
        pad_x = 16
        height = start_y + max(1, item_count) * row_h + 12
    else:
        row_h = 56
        header_y = 26
        start_y = 44
        pad_x = 24
        height = start_y + max(1, item_count) * row_h + 14

    body = [
        (
            f"<style>{SPOTIFY_FONT_FACES}\n"
            f"text {{ font-family: {SPOTIFY_FONT_STACK}; fill: #ffffff; }} "
            ".header-col { fill: #b3b3b3; font-size: 13px; font-weight: 400; } "
            ".muted { fill: #b3b3b3; font-weight: 400; } "
            ".title { font-weight: 700; fill: #ffffff; } "
            ".card-bg { fill: #121212; } "
            ".card-border { stroke: rgba(255, 255, 255, 0.08); stroke-width: 1; fill: none; } "
            "@media (prefers-color-scheme: light) { .card-border { stroke: rgba(0, 0, 0, 0.12); } } "
            ".divider { stroke: rgba(255, 255, 255, 0.1); stroke-width: 1; } "
            ".thumb-bg { fill: #282828; } "
            ".thumb-border { stroke: rgba(255, 255, 255, 0.07); stroke-width: 1; fill: none; } "
            "</style>"
        ),
        f'<defs><clipPath id="card-rp"><rect width="{width}" height="{height}" rx="12"/></clipPath></defs>',
        '<g clip-path="url(#card-rp)">',
        f'<rect width="{width}" height="{height}" class="card-bg"/>',
        "</g>",
        f'<rect width="{width}" height="{height}" rx="12" class="card-border"/>',
    ]

    # Header columns
    if compact:
        body.append(f'<text x="{pad_x}" y="{header_y}" class="header-col">#</text>')
        body.append(f'<text x="80" y="{header_y}" class="header-col">Title</text>')
        body.append(
            f'<text x="{width - pad_x}" y="{header_y}" class="header-col" text-anchor="end">Played</text>'
        )
        body.append(
            f'<line x1="{pad_x}" y1="{header_y + 8}" x2="{width - pad_x}" y2="{header_y + 8}" class="divider"/>'
        )
    else:
        body.append(f'<text x="{pad_x}" y="{header_y}" class="header-col">#</text>')
        body.append(f'<text x="100" y="{header_y}" class="header-col">Title</text>')
        body.append(f'<text x="400" y="{header_y}" class="header-col">Album</text>')
        body.append(f'<text x="590" y="{header_y}" class="header-col">Played</text>')
        body.append(
            f'<g transform="translate(720, {header_y - 12}) scale(0.85)">{CLOCK_ICON}</g>'
        )
        body.append(
            f'<line x1="{pad_x}" y1="{header_y + 8}" x2="{width - pad_x}" y2="{header_y + 8}" class="divider"/>'
        )

    if not items:
        body.append(
            f'<text x="{pad_x}" y="{start_y + 28}" class="muted" font-size="14">No recently played tracks.</text>'
        )
        return panel(width, 110, "Recently Played", "\n".join(body))

    for idx, entry in enumerate(items[:5]):
        track = entry.get("track") or {}
        name = str(track.get("name") or "Unknown")
        artists = ", ".join(a.get("name", "Unknown") for a in track.get("artists", []))
        album = str((track.get("album") or {}).get("name", ""))
        duration_ms = int(track.get("duration_ms") or 0)
        dur_str = (
            f"{duration_ms // 60000}:{duration_ms // 1000 % 60:02d}"
            if duration_ms
            else ""
        )
        played_str = format_played_at(str(entry.get("played_at") or ""), compact)

        row_y = start_y + idx * row_h
        thumb_size = 38 if compact else 40
        thumb_y = row_y + (row_h - thumb_size) // 2
        thumb_clip = f"rp-th-{idx}"
        cover_b64 = covers[idx] if idx < len(covers) else ""

        if compact:
            body.append(
                f'<text x="{pad_x}" y="{thumb_y + 24}" class="muted" font-size="13" font-variant-numeric="tabular-nums">{idx + 1}</text>'
            )
            thumb_x = pad_x + 18
            body.append(
                f'<defs><clipPath id="{thumb_clip}"><rect x="{thumb_x}" y="{thumb_y}" width="{thumb_size}" height="{thumb_size}" rx="4"/></clipPath></defs>'
            )
            body.append(
                f'<rect x="{thumb_x}" y="{thumb_y}" width="{thumb_size}" height="{thumb_size}" rx="4" class="thumb-bg"/>'
            )
            if cover_b64:
                body.append(
                    f'<image x="{thumb_x}" y="{thumb_y}" width="{thumb_size}" height="{thumb_size}" preserveAspectRatio="xMidYMid slice" clip-path="url(#{thumb_clip})" xlink:href="{escape(cover_b64, quote=True)}"/>'
                )
            body.append(
                f'<rect x="{thumb_x}" y="{thumb_y}" width="{thumb_size}" height="{thumb_size}" rx="4" class="thumb-border"/>'
            )

            tx = thumb_x + thumb_size + 10
            body.append(
                f'<text x="{tx}" y="{thumb_y + 16}" class="title" font-size="13">{escape(truncate_text(name, 28))}</text>'
            )
            body.append(
                f'<text x="{tx}" y="{thumb_y + 32}" class="muted" font-size="11">{escape(truncate_text(artists, 30))}</text>'
            )
            if played_str:
                body.append(
                    f'<text x="{width - pad_x}" y="{thumb_y + 24}" class="muted" font-size="12" text-anchor="end">{escape(played_str)}</text>'
                )
        else:
            body.append(
                f'<text x="{pad_x}" y="{thumb_y + 25}" class="muted" font-size="14" font-variant-numeric="tabular-nums">{idx + 1}</text>'
            )
            thumb_x = pad_x + 24
            body.append(
                f'<defs><clipPath id="{thumb_clip}"><rect x="{thumb_x}" y="{thumb_y}" width="{thumb_size}" height="{thumb_size}" rx="4"/></clipPath></defs>'
            )
            body.append(
                f'<rect x="{thumb_x}" y="{thumb_y}" width="{thumb_size}" height="{thumb_size}" rx="4" class="thumb-bg"/>'
            )
            if cover_b64:
                body.append(
                    f'<image x="{thumb_x}" y="{thumb_y}" width="{thumb_size}" height="{thumb_size}" preserveAspectRatio="xMidYMid slice" clip-path="url(#{thumb_clip})" xlink:href="{escape(cover_b64, quote=True)}"/>'
                )
            body.append(
                f'<rect x="{thumb_x}" y="{thumb_y}" width="{thumb_size}" height="{thumb_size}" rx="4" class="thumb-border"/>'
            )

            tx = thumb_x + thumb_size + 12
            body.append(
                f'<text x="{tx}" y="{thumb_y + 17}" class="title" font-size="14">{escape(truncate_text(name, 34))}</text>'
            )
            body.append(
                f'<text x="{tx}" y="{thumb_y + 34}" class="muted" font-size="12">{escape(truncate_text(artists, 38))}</text>'
            )
            body.append(
                f'<text x="400" y="{thumb_y + 25}" class="muted" font-size="13">{escape(truncate_text(album, 22))}</text>'
            )
            if played_str:
                body.append(
                    f'<text x="590" y="{thumb_y + 25}" class="muted" font-size="13">{escape(played_str)}</text>'
                )
            if dur_str:
                body.append(
                    f'<text x="736" y="{thumb_y + 25}" class="muted" font-size="13" font-variant-numeric="tabular-nums" text-anchor="end">{dur_str}</text>'
                )

    title_summary = "Recently Played: " + ", ".join(
        str((e.get("track") or {}).get("name") or "Unknown") for e in items[:5]
    )
    return panel(width, height, title_summary, "\n".join(body))


def render_on_repeat(
    tracks: list[dict[str, Any]],
    artists: list[dict[str, Any]],
    track_covers: list[str] | None = None,
    artist_covers: list[str] | None = None,
    compact: bool = False,
) -> str:
    track_covers = track_covers or []
    artist_covers = artist_covers or []
    width = 400 if compact else 760
    count = max(len(tracks[:5]), len(artists[:5]))

    if compact:
        row_h = 50
        sec_header_h = 24
        pad_x = 16
        height = (
            16
            + sec_header_h
            + len(tracks[:5]) * row_h
            + 14
            + sec_header_h
            + len(artists[:5]) * row_h
            + 14
        )
    else:
        row_h = 54
        pad_x = 24
        height = 24 + 20 + max(count, 1) * row_h + 14

    body = [
        (
            f"<style>{SPOTIFY_FONT_FACES}\n"
            f"text {{ font-family: {SPOTIFY_FONT_STACK}; fill: #ffffff; }} "
            ".header-col { fill: #b3b3b3; font-size: 12px; font-weight: 700; letter-spacing: 0.5px; } "
            ".muted { fill: #b3b3b3; font-weight: 400; } "
            ".title { font-weight: 700; fill: #ffffff; } "
            ".rank { fill: #1ed760; font-weight: 700; font-variant-numeric: tabular-nums; } "
            ".card-bg { fill: #121212; } "
            ".card-border { stroke: rgba(255, 255, 255, 0.08); stroke-width: 1; fill: none; } "
            "@media (prefers-color-scheme: light) { .card-border { stroke: rgba(0, 0, 0, 0.12); } } "
            ".divider { stroke: rgba(255, 255, 255, 0.1); stroke-width: 1; } "
            ".thumb-bg { fill: #282828; } "
            ".thumb-border { stroke: rgba(255, 255, 255, 0.07); stroke-width: 1; fill: none; } "
            "</style>"
        ),
        f'<defs><clipPath id="card-or"><rect width="{width}" height="{height}" rx="12"/></clipPath></defs>',
        '<g clip-path="url(#card-or)">',
        f'<rect width="{width}" height="{height}" class="card-bg"/>',
        "</g>",
        f'<rect width="{width}" height="{height}" rx="12" class="card-border"/>',
    ]

    if not compact:
        col1_w = 380
        col1_x = pad_x
        div_x = pad_x + col1_w + 12
        col2_x = div_x + 16

        body.append(f'<text x="{col1_x}" y="26" class="header-col">TOP TRACKS</text>')
        body.append(f'<text x="{col2_x}" y="26" class="header-col">TOP ARTISTS</text>')
        body.append(
            f'<line x1="{col1_x}" y1="36" x2="{col1_x + col1_w}" y2="36" class="divider"/>'
        )
        body.append(
            f'<line x1="{col2_x}" y1="36" x2="{width - pad_x}" y2="36" class="divider"/>'
        )
        body.append(
            f'<line x1="{div_x}" y1="16" x2="{div_x}" y2="{height - 16}" class="divider"/>'
        )

        start_y = 44
        for idx, trk in enumerate(tracks[:5]):
            t_name = str(trk.get("name") or "Unknown")
            t_art = ", ".join(a.get("name", "Unknown") for a in trk.get("artists", []))
            row_y = start_y + idx * row_h
            t_cover = track_covers[idx] if idx < len(track_covers) else ""
            thumb_clip = f"trk-th-{idx}"

            body.append(
                f'<text x="{col1_x}" y="{row_y + 26}" class="rank" font-size="14">{idx + 1}</text>'
            )
            thumb_x = col1_x + 24
            thumb_y = row_y + 6
            body.append(
                f'<defs><clipPath id="{thumb_clip}"><rect x="{thumb_x}" y="{thumb_y}" width="40" height="40" rx="4"/></clipPath></defs>'
            )
            body.append(
                f'<rect x="{thumb_x}" y="{thumb_y}" width="40" height="40" rx="4" class="thumb-bg"/>'
            )
            if t_cover:
                body.append(
                    f'<image x="{thumb_x}" y="{thumb_y}" width="40" height="40" preserveAspectRatio="xMidYMid slice" clip-path="url(#{thumb_clip})" xlink:href="{escape(t_cover, quote=True)}"/>'
                )
            body.append(
                f'<rect x="{thumb_x}" y="{thumb_y}" width="40" height="40" rx="4" class="thumb-border"/>'
            )

            tx = thumb_x + 40 + 12
            body.append(
                f'<text x="{tx}" y="{row_y + 20}" class="title" font-size="13">{escape(truncate_text(t_name, 36))}</text>'
            )
            body.append(
                f'<text x="{tx}" y="{row_y + 36}" class="muted" font-size="11">{escape(truncate_text(t_art, 40))}</text>'
            )

        for idx, art in enumerate(artists[:5]):
            a_name = str(art.get("name") or "Unknown")
            genres = art.get("genres", [])
            a_genre = genres[0].title() if genres else "Artist"
            row_y = start_y + idx * row_h
            a_cover = artist_covers[idx] if idx < len(artist_covers) else ""
            thumb_clip = f"art-th-{idx}"

            body.append(
                f'<text x="{col2_x}" y="{row_y + 26}" class="rank" font-size="14">{idx + 1}</text>'
            )
            thumb_x = col2_x + 24
            thumb_y = row_y + 6
            body.append(
                f'<defs><clipPath id="{thumb_clip}"><circle cx="{thumb_x + 20}" cy="{thumb_y + 20}" r="20"/></clipPath></defs>'
            )
            body.append(
                f'<circle cx="{thumb_x + 20}" cy="{thumb_y + 20}" r="20" class="thumb-bg"/>'
            )
            if a_cover:
                body.append(
                    f'<image x="{thumb_x}" y="{thumb_y}" width="40" height="40" preserveAspectRatio="xMidYMid slice" clip-path="url(#{thumb_clip})" xlink:href="{escape(a_cover, quote=True)}"/>'
                )
            body.append(
                f'<circle cx="{thumb_x + 20}" cy="{thumb_y + 20}" r="20" class="thumb-border"/>'
            )

            tx = thumb_x + 40 + 12
            body.append(
                f'<text x="{tx}" y="{row_y + 20}" class="title" font-size="13">{escape(truncate_text(a_name, 26))}</text>'
            )
            body.append(
                f'<text x="{tx}" y="{row_y + 36}" class="muted" font-size="11">{escape(truncate_text(a_genre, 28))}</text>'
            )
    else:
        start_y = 22
        body.append(
            f'<text x="{pad_x}" y="{start_y}" class="header-col" font-size="11" font-weight="700" letter-spacing="0.5px">TOP TRACKS</text>'
        )
        body.append(
            f'<line x1="{pad_x}" y1="{start_y + 8}" x2="{width - pad_x}" y2="{start_y + 8}" class="divider"/>'
        )
        track_start = start_y + 14
        for idx, trk in enumerate(tracks[:5]):
            t_name = str(trk.get("name") or "Unknown")
            t_art = ", ".join(a.get("name", "Unknown") for a in trk.get("artists", []))
            row_y = track_start + idx * row_h
            t_cover = track_covers[idx] if idx < len(track_covers) else ""
            thumb_clip = f"m-trk-th-{idx}"

            body.append(
                f'<text x="{pad_x}" y="{row_y + 24}" class="rank" font-size="12">{idx + 1}</text>'
            )
            thumb_x = pad_x + 24
            thumb_y = row_y + 4
            body.append(
                f'<defs><clipPath id="{thumb_clip}"><rect x="{thumb_x}" y="{thumb_y}" width="36" height="36" rx="4"/></clipPath></defs>'
            )
            body.append(
                f'<rect x="{thumb_x}" y="{thumb_y}" width="36" height="36" rx="4" class="thumb-bg"/>'
            )
            if t_cover:
                body.append(
                    f'<image x="{thumb_x}" y="{thumb_y}" width="36" height="36" preserveAspectRatio="xMidYMid slice" clip-path="url(#{thumb_clip})" xlink:href="{escape(t_cover, quote=True)}"/>'
                )
            body.append(
                f'<rect x="{thumb_x}" y="{thumb_y}" width="36" height="36" rx="4" class="thumb-border"/>'
            )

            tx = thumb_x + 36 + 10
            body.append(
                f'<text x="{tx}" y="{row_y + 18}" class="title" font-size="13">{escape(truncate_text(t_name, 36))}</text>'
            )
            body.append(
                f'<text x="{tx}" y="{row_y + 34}" class="muted" font-size="11">{escape(truncate_text(t_art, 40))}</text>'
            )

        art_header_y = track_start + len(tracks[:5]) * row_h + 12
        body.append(
            f'<line x1="{pad_x}" y1="{art_header_y}" x2="{width - pad_x}" y2="{art_header_y}" class="divider"/>'
        )
        body.append(
            f'<text x="{pad_x}" y="{art_header_y + 16}" class="header-col" font-size="11" font-weight="700" letter-spacing="0.5px">TOP ARTISTS</text>'
        )
        body.append(
            f'<line x1="{pad_x}" y1="{art_header_y + 24}" x2="{width - pad_x}" y2="{art_header_y + 24}" class="divider"/>'
        )
        art_start = art_header_y + 30
        for idx, art in enumerate(artists[:5]):
            a_name = str(art.get("name") or "Unknown")
            genres = art.get("genres", [])
            a_genre = genres[0].title() if genres else "Artist"
            row_y = art_start + idx * row_h
            a_cover = artist_covers[idx] if idx < len(artist_covers) else ""
            thumb_clip = f"m-art-th-{idx}"

            body.append(
                f'<text x="{pad_x}" y="{row_y + 24}" class="rank" font-size="12">{idx + 1}</text>'
            )
            thumb_x = pad_x + 24
            thumb_y = row_y + 4
            body.append(
                f'<defs><clipPath id="{thumb_clip}"><circle cx="{thumb_x + 18}" cy="{thumb_y + 18}" r="18"/></clipPath></defs>'
            )
            body.append(
                f'<circle cx="{thumb_x + 18}" cy="{thumb_y + 18}" r="18" class="thumb-bg"/>'
            )
            if a_cover:
                body.append(
                    f'<image x="{thumb_x}" y="{thumb_y}" width="36" height="36" preserveAspectRatio="xMidYMid slice" clip-path="url(#{thumb_clip})" xlink:href="{escape(a_cover, quote=True)}"/>'
                )
            body.append(
                f'<circle cx="{thumb_x + 18}" cy="{thumb_y + 18}" r="18" class="thumb-border"/>'
            )

            tx = thumb_x + 36 + 10
            body.append(
                f'<text x="{tx}" y="{row_y + 18}" class="title" font-size="13">{escape(truncate_text(a_name, 36))}</text>'
            )
            body.append(
                f'<text x="{tx}" y="{row_y + 34}" class="muted" font-size="11">{escape(truncate_text(a_genre, 40))}</text>'
            )

    title_summary = "On Repeat: " + ", ".join(
        str(t.get("name") or "Unknown") for t in tracks[:5]
    )
    return panel(width, height, title_summary, "\n".join(body))


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
