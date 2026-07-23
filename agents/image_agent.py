"""
image_agent.py
Pulls topic-relevant, royalty-free stock photos from the Pexels API instead
of generating AI images — avoids all billing/quota issues. Downloads 4
varied images per topic so video_agent.py can apply Ken Burns zoom effects.

Requires: PEXELS_API_KEY environment variable, requests package.
    pip install requests --break-system-packages

Get a free key at https://www.pexels.com/api/ (no billing, no card needed).
"""
import os
import requests
from pathlib import Path

GENERATED_MEDIA_DIR = os.getenv("GENERATED_MEDIA_DIR", "./generated_media")
IMAGE_COUNT_PER_TOPIC = 4
PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"

_session = None


def _get_session():
    global _session
    if _session is None:
        api_key = os.environ.get("PEXELS_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "PEXELS_API_KEY environment variable not set. "
                "Get a free key at https://www.pexels.com/api/ and run: "
                "export PEXELS_API_KEY='your_key_here'"
            )
        s = requests.Session()
        s.headers.update({"Authorization": api_key, "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
        _session = s
    return _session


def _search_photos(query: str, count: int) -> list[str]:
    """Returns a list of large-size image URLs for the query."""
    session = _get_session()
    resp = session.get(
        PEXELS_SEARCH_URL,
        params={"query": query, "per_page": count, "orientation": "portrait"},
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"[image_agent DEBUG] query={query!r} status={resp.status_code} body={resp.text!r} url={resp.url!r}")
    resp.raise_for_status()
    data = resp.json()
    photos = data.get("photos", [])
    if not photos:
        raise RuntimeError(f"No Pexels results for query: {query!r}")
    return [p["src"]["large2x"] for p in photos]


def generate_images_for_topic(topic_id: str, topic_title: str,
                                count: int = IMAGE_COUNT_PER_TOPIC) -> list[str]:
    """
    Fetches `count` topic-relevant stock photos and saves them to
    generated_media/<topic_id>/img_N.jpg. Returns list of file paths.
    """
    session = _get_session()
    out_dir = Path(GENERATED_MEDIA_DIR) / topic_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Pexels needs a real search term, not a full sentence — trim the topic
    # down to a few keywords for better hit rate.
    query = " ".join(topic_title.split()[:4])

    try:
        urls = _search_photos(query, count)
    except RuntimeError:
        # Fallback to a generic query if the specific topic has no results
        urls = _search_photos("computer repair shop", count)

    # Pad out if fewer results than requested, by repeating the query
    while len(urls) < count:
        urls.append(urls[len(urls) % max(len(urls), 1)])

    paths = []
    for i, url in enumerate(urls[:count]):
        img_resp = session.get(url, timeout=20)
        img_resp.raise_for_status()

        img_path = out_dir / f"img_{i+1}.jpg"
        img_path.write_bytes(img_resp.content)
        paths.append(str(img_path))
        print(f"[image_agent] downloaded {img_path}")

    return paths
