#!/usr/bin/env python3
"""
Find YouTube thumbnail outliers — videos that massively outperformed their channel's median.

Searches across multiple niches (not just the video's topic) to find creative inspiration
from channels where a specific thumbnail/title combo broke through.

Uses the YouTube Data API v3 to:
1. Search for videos in each niche
2. Fetch channel stats (subscriber count)
3. Fetch recent videos per channel to calculate median views
4. Score each video as a multiple of its channel's median
5. Download thumbnails of the top outliers

Usage:
    python3 find_outliers.py \
      --topic "AI replacing operations manager" \
      --niches "AI operations" "creative filmmaking" "business storytelling" \
      --min-outlier-score 3.0 \
      --top 10

Environment:
    YOUTUBE_API_KEY must be set (or present in .env).
"""

import argparse
import datetime
import io
import json
import os
import re
import statistics
import sys
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
from PIL import Image

# Enable AVIF support
try:
    import pillow_avif  # noqa: F401
except ImportError:
    pass

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
YOUTUBE_THUMBNAIL_DOMAINS = ("https://i.ytimg.com/", "https://img.youtube.com/")
_quota_used = 0  # running quota counter


def youtube_api_get(endpoint, params, api_key):
    """Make a GET request to the YouTube Data API v3."""
    global _quota_used
    # search.list costs 100 units, everything else costs 1-3
    _quota_used += 100 if endpoint == "search" else 3
    params["key"] = api_key
    query = urllib.parse.urlencode(params)
    url = f"{YOUTUBE_API_BASE}/{endpoint}?{query}"

    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        if e.code == 403 and "quotaExceeded" in body:
            print("Error: YouTube API daily quota exceeded. Try again tomorrow.", file=sys.stderr)
            sys.exit(1)
        # Redact API key from error output
        safe_body = body.replace(api_key, "REDACTED") if api_key in body else body
        print(f"Error: YouTube API returned {e.code}: {safe_body[:200]}", file=sys.stderr)
        return None
    except Exception as e:
        # Redact API key from exception messages (urllib may include the full URL)
        msg = str(e).replace(api_key, "REDACTED") if api_key in str(e) else str(e)
        print(f"Error: YouTube API request failed: {msg}", file=sys.stderr)
        return None


def search_videos(query, api_key, max_results=50):
    """Search YouTube for videos matching a query. Returns list of video items.

    Searches with both viewCount and relevance ordering to catch both viral hits
    and newer emerging content. Filters to medium (4-20 min) and long (>20 min)
    videos only — excludes Shorts, which have inflated view counts and
    auto-generated thumbnails.
    """
    results = []
    seen_ids = set()
    for order in ("viewCount", "relevance"):
        for duration in ("medium", "long"):
            data = youtube_api_get("search", {
                "part": "snippet",
                "q": query,
                "type": "video",
                "order": order,
                "videoDuration": duration,
                "maxResults": min(max_results, 50),
            }, api_key)
            if data and "items" in data:
                for item in data["items"]:
                    vid = item.get("id", {}).get("videoId")
                    if vid and vid not in seen_ids:
                        seen_ids.add(vid)
                        results.append(item)
    return results


def get_video_stats(video_ids, api_key):
    """Get view counts for a list of video IDs. Returns dict of video_id -> view_count."""
    if not video_ids:
        return {}

    # API accepts up to 50 IDs at once
    data = youtube_api_get("videos", {
        "part": "statistics",
        "id": ",".join(video_ids[:50]),
    }, api_key)

    if not data or "items" not in data:
        return {}

    stats = {}
    for item in data["items"]:
        view_count = int(item["statistics"].get("viewCount", 0))
        stats[item["id"]] = view_count
    return stats


def get_channel_info(channel_id, api_key):
    """Get channel subscriber count and uploads playlist ID."""
    data = youtube_api_get("channels", {
        "part": "statistics,contentDetails",
        "id": channel_id,
    }, api_key)

    if not data or not data.get("items"):
        return None

    item = data["items"][0]
    sub_count = int(item["statistics"].get("subscriberCount", 0))
    uploads_playlist = item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
    return {"subscriber_count": sub_count, "uploads_playlist": uploads_playlist}


def get_channel_recent_videos(uploads_playlist_id, api_key, max_results=15):
    """Get recent video IDs from a channel's uploads playlist, then fetch their view counts.

    Uses playlistItems endpoint (1 quota unit) instead of search endpoint (100 units).
    The uploads playlist ID is available from channels.list with part=contentDetails.
    """
    if not uploads_playlist_id:
        return []

    data = youtube_api_get("playlistItems", {
        "part": "contentDetails",
        "playlistId": uploads_playlist_id,
        "maxResults": min(max_results, 50),
    }, api_key)

    if not data or "items" not in data:
        return []

    video_ids = [item["contentDetails"]["videoId"] for item in data["items"] if "videoId" in item.get("contentDetails", {})]
    if not video_ids:
        return []

    stats = get_video_stats(video_ids, api_key)
    return [stats.get(vid, 0) for vid in video_ids if vid in stats]


def calculate_median_views(view_counts):
    """Calculate median view count, filtering out zeros."""
    filtered = [v for v in view_counts if v > 0]
    if not filtered:
        return 0
    return statistics.median(filtered)


def download_thumbnail(url, output_path):
    """Download a thumbnail image, convert to JPEG via Pillow."""
    if not any(url.startswith(domain) for domain in YOUTUBE_THUMBNAIL_DOMAINS):
        print(f"  Warning: Skipping non-YouTube thumbnail URL: {url[:80]}", file=sys.stderr)
        return False
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()

        if len(data) < 100:
            return False

        img = Image.open(io.BytesIO(data))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output_path), "JPEG", quality=90)
        return True
    except Exception as e:
        print(f"  Warning: Failed to download thumbnail: {e}", file=sys.stderr)
        return False


def get_best_thumbnail_url(thumbnails):
    """Pick the highest resolution thumbnail URL from the API response."""
    for key in ("maxres", "standard", "high", "medium", "default"):
        if key in thumbnails:
            return thumbnails[key]["url"]
    return None


def slugify(text, max_len=40):
    """Convert text to a filename-safe slug."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text).strip("-")
    return text[:max_len]


def main():
    parser = argparse.ArgumentParser(
        description="Find YouTube thumbnail outliers — videos that outperformed their channel's median"
    )
    parser.add_argument("--topic", required=True, help="Video topic (used as primary search query)")
    parser.add_argument(
        "--niches", nargs="*", default=[],
        help="Additional niche search queries for cross-niche inspiration (e.g., 'creative filmmaking' 'design storytelling')"
    )
    parser.add_argument("--min-outlier-score", type=float, default=3.0, help="Minimum outlier score to include (default: 3.0)")
    parser.add_argument("--top", type=int, default=10, help="Number of top outliers to return (default: 10)")
    parser.add_argument(
        "--output-dir", default=None,
        help="Output directory for downloaded thumbnails (default: output/YYYY-MM-DD/outliers)"
    )
    args = parser.parse_args()

    load_dotenv(find_dotenv(usecwd=True))

    # Default output dir: if not specified, caller must pass --output-dir
    # (prompt.md instructs passing the video-specific outliers path)
    if args.output_dir is None:
        today = datetime.date.today().isoformat()
        args.output_dir = f"output/{today}/outliers"

    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("Error: YOUTUBE_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    # Build search queries: topic + additional niches
    queries = [args.topic] + args.niches

    print(f"Searching {len(queries)} niche(s) for outliers...\n", file=sys.stderr)

    all_candidates = []
    seen_channels = {}  # cache channel stats to avoid duplicate API calls
    seen_video_ids = set()  # deduplicate videos across niches

    for query in queries:
        print(f"Searching: \"{query}\"", file=sys.stderr)
        videos = search_videos(query, api_key)

        if not videos:
            print(f"  No results found\n", file=sys.stderr)
            continue

        # Get view counts for all found videos
        video_ids = [v["id"]["videoId"] for v in videos if "videoId" in v.get("id", {})]
        video_stats = get_video_stats(video_ids, api_key)

        print(f"  Found {len(videos)} videos, analyzing channels...", file=sys.stderr)

        for video in videos:
            video_id = video.get("id", {}).get("videoId")
            if not video_id or video_id not in video_stats:
                continue

            # Skip duplicate videos found in multiple niche searches
            if video_id in seen_video_ids:
                continue
            seen_video_ids.add(video_id)

            channel_id = video["snippet"]["channelId"]
            title = video["snippet"]["title"]
            views = video_stats[video_id]

            if views < 1000:
                continue  # skip very low view count videos

            # Get or cache channel info
            if channel_id not in seen_channels:
                channel_info = get_channel_info(channel_id, api_key)
                if not channel_info:
                    continue

                recent_views = get_channel_recent_videos(channel_info["uploads_playlist"], api_key, max_results=15)
                median = calculate_median_views(recent_views)

                seen_channels[channel_id] = {
                    "name": video["snippet"]["channelTitle"],
                    "subs": channel_info["subscriber_count"],
                    "median_views": median,
                }

            channel = seen_channels[channel_id]

            if channel["median_views"] <= 0:
                continue

            outlier_score = views / channel["median_views"]

            if outlier_score > 100:
                continue  # skip — score this high means broken median, not a real outlier

            if outlier_score >= args.min_outlier_score:
                all_candidates.append({
                    "title": title,
                    "video_id": video_id,
                    "views": views,
                    "channel": channel["name"],
                    "channel_id": channel_id,
                    "subs": channel["subs"],
                    "median_views": int(channel["median_views"]),
                    "outlier_score": round(outlier_score, 1),
                    "niche": query,
                    "thumbnail_url": get_best_thumbnail_url(video["snippet"].get("thumbnails", {})),
                })

        print(f"  Done\n", file=sys.stderr)

    if not all_candidates:
        print("No outliers found above the minimum score threshold.", file=sys.stderr)
        print("[]")  # empty manifest — not an error, just no results
        sys.exit(0)

    # Cap results per channel — mega-channels like TEDx dominate otherwise
    channel_counts = {}
    filtered_candidates = []
    for c in sorted(all_candidates, key=lambda x: x["outlier_score"], reverse=True):
        ch = c["channel_id"]
        channel_counts[ch] = channel_counts.get(ch, 0) + 1
        if channel_counts[ch] <= 2:
            filtered_candidates.append(c)
    all_candidates = filtered_candidates

    # Ensure niche diversity — guarantee at least 3 from primary topic
    topic_niche = queries[0]
    topic_results = [c for c in all_candidates if c["niche"] == topic_niche]
    other_results = [c for c in all_candidates if c["niche"] != topic_niche]
    min_topic = min(3, len(topic_results))
    remaining_slots = args.top - min_topic
    diverse_top = topic_results[:min_topic] + sorted(other_results, key=lambda x: x["outlier_score"], reverse=True)[:remaining_slots]
    diverse_top.sort(key=lambda x: x["outlier_score"], reverse=True)
    all_candidates = diverse_top

    # Sort by outlier score, take top N
    top = all_candidates[:args.top]

    # Print results to stderr (human-readable)
    print(f"Found {len(all_candidates)} outlier(s), showing top {len(top)}:\n", file=sys.stderr)
    for i, c in enumerate(top):
        print(
            f"  {i+1}. Outlier Score {c['outlier_score']}x — \"{c['title']}\" ({c['views']:,} views)\n"
            f"     Channel: {c['channel']} ({c['subs']:,} subs, median {c['median_views']:,} views)\n"
            f"     Niche: {c['niche']}\n",
            file=sys.stderr,
        )

    # Download thumbnails
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    for i, c in enumerate(top):
        if not c["thumbnail_url"]:
            continue

        filename = f"outlier-{i+1}-{slugify(c['title'])}.jpg"
        output_path = output_dir / filename

        print(f"  Downloading thumbnail {i+1}: {c['title'][:50]}...", file=sys.stderr)
        if download_thumbnail(c["thumbnail_url"], output_path):
            c["path"] = str(output_path)
            manifest.append(c)

    if not manifest:
        print("Warning: Failed to download any thumbnails.", file=sys.stderr)
        print("[]")
        sys.exit(0)

    print(f"\nDownloaded {len(manifest)} outlier thumbnails to {output_dir}/", file=sys.stderr)

    # Print JSON manifest to stdout (machine-readable)
    # Clean up fields: convert video_id to URL, remove internal IDs
    for item in manifest:
        item["url"] = f"https://youtube.com/watch?v={item.pop('video_id', '')}"
        item.pop("thumbnail_url", None)
        item.pop("channel_id", None)

    print(json.dumps(manifest, indent=2))

    print(f"\nEstimated YouTube API quota used: ~{_quota_used} units (daily limit: 10,000)", file=sys.stderr)


if __name__ == "__main__":
    main()
