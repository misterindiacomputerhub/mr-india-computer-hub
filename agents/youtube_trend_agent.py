import json
"""
Trending Topic Finder
Finds YouTube videos published in the last N hours that match the shop's
niche keywords, as a proxy for "trending topics" relevant to the channel.

Requires YOUTUBE_API_KEY in .env (separate from the OAuth client_secret.json
used by upload_agent.py — this is a simple API-key-based read call).
"""

import os
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

# TODO: adjust to match your shop's actual niches / data/services.json categories
NICHE_KEYWORDS = [
    "computer repair",
    "printer repair",
    "CCTV installation",
    "cyber cafe services",
    "networking setup",
    "computer accessories",
    "photography services",
]


_trend_cache = {"results": None, "fetched_at": None}
_CACHE_TTL_HOURS = 3


def find_trending_topics(hours=24, keywords=None, max_per_keyword=5, force_refresh=False):
    """
    Returns a list of dicts:
    {keyword, topic_title, channel, views, published_at, url}
    sorted by views descending.

    Results are cached in-process for _CACHE_TTL_HOURS to avoid burning
    YouTube API quota (each keyword search costs ~100 units; with several
    niche keywords, repeated clicks can exhaust the daily 10,000-unit quota
    in a handful of clicks). Pass force_refresh=True to bypass the cache.
    """
    if not YOUTUBE_API_KEY:
        raise RuntimeError("YOUTUBE_API_KEY not set in .env")

    now = datetime.now(timezone.utc)

    # Check in-memory cache first (fastest, survives within one process run)
    if (
        not force_refresh
        and _trend_cache["results"] is not None
        and _trend_cache["fetched_at"] is not None
        and (now - _trend_cache["fetched_at"]) < timedelta(hours=_CACHE_TTL_HOURS)
    ):
        print(f"[youtube_trend_agent] Using in-memory cached results from {_trend_cache['fetched_at'].isoformat()}")
        return _trend_cache["results"]

    # Fall back to Neon-backed cache (survives Render sleep/restart)
    if not force_refresh:
        from database import get_trend_cache
        cached_json = get_trend_cache(max_age_hours=_CACHE_TTL_HOURS)
        if cached_json:
            print("[youtube_trend_agent] Using Neon-cached results (survived restart)")
            results = json.loads(cached_json)
            _trend_cache["results"] = results
            _trend_cache["fetched_at"] = now
            return results

    keywords = keywords or NICHE_KEYWORDS
    published_after = (
        datetime.now(timezone.utc) - timedelta(hours=hours)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    results = []
    for kw in keywords:
        params = {
            "part": "snippet",
            "q": kw,
            "type": "video",
            "order": "viewCount",
            "publishedAfter": published_after,
            "maxResults": max_per_keyword,
            "key": YOUTUBE_API_KEY,
        }
        resp = requests.get(SEARCH_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        video_ids = [item["id"]["videoId"] for item in data.get("items", [])]
        stats = _get_view_counts(video_ids) if video_ids else {}

        for item in data.get("items", []):
            vid = item["id"]["videoId"]
            results.append({
                "keyword": kw,
                "topic_title": item["snippet"]["title"],
                "channel": item["snippet"]["channelTitle"],
                "views": stats.get(vid, 0),
                "published_at": item["snippet"]["publishedAt"],
                "url": f"https://www.youtube.com/watch?v={vid}",
            })

    results.sort(key=lambda x: x["views"], reverse=True)
    _trend_cache["results"] = results
    _trend_cache["fetched_at"] = now
    try:
        from database import save_trend_cache
        save_trend_cache(json.dumps(results))
    except Exception as e:
        print(f"[youtube_trend_agent] WARNING: failed to save trend cache to Neon: {e}")
    return results


def _get_view_counts(video_ids):
    if not video_ids:
        return {}
    params = {
        "part": "statistics",
        "id": ",".join(video_ids),
        "key": YOUTUBE_API_KEY,
    }
    resp = requests.get(
        "https://www.googleapis.com/youtube/v3/videos", params=params, timeout=15
    )
    resp.raise_for_status()
    out = {}
    for item in resp.json().get("items", []):
        out[item["id"]] = int(item["statistics"].get("viewCount", 0))
    return out
