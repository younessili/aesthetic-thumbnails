#!/usr/bin/env python3
"""
Generate a YouTube thumbnail preview HTML showing thumbnail + title
across multiple YouTube contexts (Home Large, Sidebar, Mobile, TV).

Each context row has its own realistic sizing so you can see how the
thumbnail reads at different scales. Titles shown side-by-side for comparison.

Supports multiple thumbnails (one per title) or a single thumbnail for all.

Usage:
    # Same thumbnail, 3 title options:
    python3 preview_thumbnail.py \
        --thumbnail path/to/thumb.png \
        --titles "Title 1" "Title 2" "Title 3" \
        --output path/to/preview.html

    # Different thumbnail per option:
    python3 preview_thumbnail.py \
        --thumbnail path/to/a.png path/to/b.png path/to/c.png \
        --titles "Title A" "Title B" "Title C" \
        --output path/to/preview.html
"""

import argparse
import base64
import html
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Generate YouTube thumbnail preview HTML")
    parser.add_argument("--thumbnail", required=True, nargs="+", help="Path(s) to thumbnail image(s). One for all titles, or one per title.")
    parser.add_argument("--titles", required=True, nargs="+", help="1-3 title options")
    parser.add_argument("--output", required=True, help="Output HTML file path")
    parser.add_argument("--channel-name", default="Your Channel", help="Channel name for mockup")
    parser.add_argument("--timestamp", default="14:56", help="Video duration timestamp")
    return parser.parse_args()


def encode_image(path):
    """Read image file and return base64 data URI."""
    p = Path(path)
    if not p.exists():
        print(f"Error: Image not found: {path}", file=sys.stderr)
        sys.exit(1)
    suffix = p.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    with open(p, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{data}"


def build_home_card(title, thumb_uri, channel, ts, idx):
    title = html.escape(title)
    channel = html.escape(channel)
    return f"""
            <div class="card home-card">
                <div class="card-label"><span class="badge">{idx}</span></div>
                <div class="tw">
                    <img src="{thumb_uri}" alt="thumbnail">
                    <span class="ts">{ts}</span>
                </div>
                <div class="meta">
                    <div class="av"></div>
                    <div class="mt">
                        <div class="vt">{title}</div>
                        <div class="ms">{channel}</div>
                        <div class="ms">123K views &middot; 1 hour ago</div>
                    </div>
                </div>
            </div>"""


def build_sidebar_card(title, thumb_uri, channel, ts, idx):
    title = html.escape(title)
    channel = html.escape(channel)
    return f"""
            <div class="card sb-card">
                <div class="card-label"><span class="badge badge-sm">{idx}</span></div>
                <div class="sb-layout">
                    <div class="tw sb-tw">
                        <img src="{thumb_uri}" alt="thumbnail">
                        <span class="ts ts-s">{ts}</span>
                    </div>
                    <div class="sb-meta">
                        <div class="vt vt-s">{title}</div>
                        <div class="ms ms-s">{channel}</div>
                        <div class="ms ms-s">123K views &middot; 1 hour ago</div>
                    </div>
                </div>
            </div>"""


def build_mobile_card(title, thumb_uri, channel, ts, idx):
    title = html.escape(title)
    channel = html.escape(channel)
    return f"""
            <div class="mob-outer">
                <div class="card-label"><span class="badge">{idx}</span></div>
                <div class="mob-frame">
                    <div class="tw mob-tw">
                        <img src="{thumb_uri}" alt="thumbnail">
                        <span class="ts">{ts}</span>
                    </div>
                    <div class="meta mob-meta">
                        <div class="av av-s"></div>
                        <div class="mt">
                            <div class="vt">{title}</div>
                            <div class="ms ms-s">{channel} &middot; 123K views &middot; 1 hour ago</div>
                        </div>
                    </div>
                </div>
            </div>"""


def build_tv_card(title, thumb_uri, channel, ts, idx):
    title = html.escape(title)
    channel = html.escape(channel)
    return f"""
            <div class="card tv-card">
                <div class="card-label"><span class="badge badge-lg">{idx}</span></div>
                <div class="tw">
                    <img src="{thumb_uri}" alt="thumbnail">
                    <span class="ts ts-l">{ts}</span>
                </div>
                <div class="tv-info">
                    <div class="vt vt-l">{title}</div>
                    <div class="ms">{channel}</div>
                    <div class="ms">123K views &middot; 1 hour ago</div>
                </div>
            </div>"""


CSS = """
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500&display=swap');
  *{margin:0;padding:0;box-sizing:border-box}

  body {
    background: #131313;
    color: #E2E2E2;
    font-family: "Inter", sans-serif;
    padding: 48px 40px;
  }

  /* ---- Header ---- */
  .hdr { max-width: 1600px; margin: 0 auto 56px; }
  .hdr h1 {
    font-family: "Space Grotesk", sans-serif;
    font-size: 1.75rem;
    font-weight: 700;
    letter-spacing: -0.03em;
  }
  .hdr h1 em {
    font-style: normal;
    background: linear-gradient(135deg, #FFE9BD, #FFC72C);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  .hdr p { font-size: 0.875rem; color: #8A8A8A; margin-top: 6px; }
  .finder-link {
    color: #8A8A8A;
    text-decoration: none;
    margin-left: 6px;
    padding: 2px 8px;
    background: #1B1B1B;
    border-radius: 2px;
    font-size: 0.75rem;
    transition: color 0.15s;
  }
  .finder-link:hover { color: #FFC72C; }

  /* ---- Context rows ---- */
  .ctx {
    max-width: 1600px;
    margin: 0 auto 56px;
  }
  .ctx-lbl {
    font-family: "Space Grotesk", sans-serif;
    font-size: 0.6875rem;
    font-weight: 500;
    color: #FFC72C;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 20px;
    padding-bottom: 12px;
    background: linear-gradient(to right, rgba(255,199,44,0.08), transparent 60%);
    padding: 8px 12px;
    border-radius: 2px;
  }
  .ctx-cards {
    display: flex;
    gap: 20px;
    flex-wrap: wrap;
    align-items: flex-start;
  }

  /* ---- Badge (above card, not overlapping image) ---- */
  .card-label {
    margin-bottom: 8px;
  }
  .badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-family: "Space Grotesk", sans-serif;
    font-size: 0.6875rem;
    font-weight: 700;
    color: #131313;
    background: linear-gradient(135deg, #FFE9BD, #FFC72C);
    width: 22px; height: 22px;
    border-radius: 2px;
  }
  .badge-sm { width: 18px; height: 18px; font-size: 0.6rem; }
  .badge-lg { width: 26px; height: 26px; font-size: 0.75rem; }

  /* ---- Cards (tonal layering) ---- */
  .card {
    background: #1B1B1B;
    border-radius: 4px;
    padding: 14px;
  }

  /* ---- Thumbnail wrap ---- */
  .tw {
    position: relative;
    border-radius: 2px;
    overflow: hidden;
    background: #0E0E0E;
  }
  .tw img { display: block; width: 100%; height: auto; }
  .ts {
    position: absolute;
    bottom: 6px; right: 6px;
    background: rgba(0,0,0,0.82);
    color: #fff;
    font-family: "Inter", sans-serif;
    font-size: 11px; font-weight: 500;
    padding: 2px 5px;
    border-radius: 2px;
  }
  .ts-s { font-size: 9px; padding: 1px 3px; bottom: 3px; right: 3px; }
  .ts-l { font-size: 14px; padding: 3px 8px; bottom: 8px; right: 8px; }

  /* ---- Meta ---- */
  .av {
    width: 32px; height: 32px;
    border-radius: 50%;
    background: #353535;
    flex-shrink: 0;
  }
  .av-s { width: 28px; height: 28px; }
  .meta {
    display: flex;
    gap: 10px;
    margin-top: 10px;
    align-items: flex-start;
  }
  .mt { flex: 1; min-width: 0; }
  .vt {
    font-size: 13px; font-weight: 500;
    color: #E2E2E2; line-height: 1.35;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .vt-s { font-size: 11px; line-height: 1.25; }
  .vt-l { font-size: 17px; line-height: 1.3; }
  .ms { font-size: 11px; color: #8A8A8A; margin-top: 1px; }
  .ms-s { font-size: 10px; }

  /* ==== HOME — capped at 340px, flexes smaller ==== */
  .home-card { width: 340px; max-width: 340px; }

  /* ==== SIDEBAR — capped at 340px, horizontal ==== */
  .sb-card { width: 340px; max-width: 340px; padding: 10px; }
  .sb-layout { display: flex; gap: 8px; align-items: flex-start; }
  .sb-tw { width: 150px; flex-shrink: 0; }
  .sb-meta { flex: 1; min-width: 0; padding-top: 1px; }

  /* ==== MOBILE — smaller than home, capped at 260px ==== */
  .mob-outer { width: 260px; max-width: 260px; }
  .mob-frame {
    background: #0E0E0E;
    border-radius: 4px;
    overflow: hidden;
  }
  .mob-tw { border-radius: 0; }
  .mob-meta {
    display: flex;
    gap: 8px;
    padding: 10px 12px 14px;
    align-items: flex-start;
  }

  /* ==== TV — fills available space, no fixed width ==== */
  .tv-card { flex: 1 1 0; min-width: 280px; padding: 16px; }
  .tv-info { margin-top: 14px; }

  /* ==== RESPONSIVE ==== */
  @media (max-width: 768px) {
    body { padding: 24px 16px; }
    .hdr h1 { font-size: 1.25rem; }
    .ctx-cards { flex-direction: column; align-items: stretch; }
    .home-card, .sb-card, .mob-outer, .tv-card {
      width: 100%; max-width: 100%;
    }
    .sb-tw { width: 40%; }
  }
"""


def build_html(thumb_uris, titles, channel_name, timestamp, thumb_dir):
    """Build HTML with rows per context, titles side-by-side."""
    n = len(titles)
    home = sidebar = mobile = tv = ""

    for i, title in enumerate(titles, 1):
        uri = thumb_uris[i - 1]
        home += build_home_card(title, uri, channel_name, timestamp, i)
        sidebar += build_sidebar_card(title, uri, channel_name, timestamp, i)
        mobile += build_mobile_card(title, uri, channel_name, timestamp, i)
        tv += build_tv_card(title, uri, channel_name, timestamp, i)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Thumbnail Preview</title>
<style>{CSS}</style>
</head>
<body>

<div class="hdr">
    <h1>Thumbnail <em>+</em> Title Preview</h1>
    <p>{n} option{"s" if n > 1 else ""} <a href="file://{thumb_dir}" class="finder-link">Open in Finder</a></p>
</div>

<div class="ctx">
    <div class="ctx-lbl">Desktop Home</div>
    <div class="ctx-cards">{home}
    </div>
</div>

<div class="ctx">
    <div class="ctx-lbl">Sidebar &mdash; Up Next</div>
    <div class="ctx-cards">{sidebar}
    </div>
</div>

<div class="ctx">
    <div class="ctx-lbl">Mobile</div>
    <div class="ctx-cards">{mobile}
    </div>
</div>

<div class="ctx">
    <div class="ctx-lbl">TV</div>
    <div class="ctx-cards">{tv}
    </div>
</div>

</body>
</html>"""


def main():
    args = parse_args()

    titles = args.titles
    thumbs = args.thumbnail

    # Resolve thumbnail URIs: one per title, or repeat single
    if len(thumbs) == 1:
        uri = encode_image(thumbs[0])
        thumb_uris = [uri] * len(titles)
    elif len(thumbs) == len(titles):
        thumb_uris = [encode_image(t) for t in thumbs]
    else:
        print(f"Error: got {len(thumbs)} thumbnails but {len(titles)} titles. Provide 1 or {len(titles)}.", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Finder link opens where the thumbnail PNGs live.
    # Single thumbnail: its parent dir. Multiple: their common parent.
    thumb_paths = [Path(t).resolve() for t in thumbs]
    if len(thumb_paths) == 1:
        thumb_dir = str(thumb_paths[0].parent)
    else:
        # Find common ancestor of all thumbnail paths
        parts = [p.parts for p in thumb_paths]
        common = []
        for level in zip(*parts):
            if len(set(level)) == 1:
                common.append(level[0])
            else:
                break
        thumb_dir = str(Path(*common)) if common else str(thumb_paths[0].parent)

    html_content = build_html(thumb_uris, titles, args.channel_name, args.timestamp, thumb_dir)
    output_path.write_text(html_content)
    print(f"Preview saved to: {output_path}")


if __name__ == "__main__":
    main()
