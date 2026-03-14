import requests
import hashlib
from django.conf import settings
from django.core.cache import cache

YOUTUBE_URL = "https://www.googleapis.com/youtube/v3/search"


def get_youtube_videos(query, max_results=6):
    cache_key = "yt:%s:%s" % (
        hashlib.md5(query.encode("utf-8")).hexdigest(),
        max_results,
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    api_key = str(getattr(settings, "YOUTUBE_API_KEY", "")).strip()
    if not api_key:
        return []

    params = {
        "part": "snippet",
        "q": query,
        "key": api_key,
        "type": "video",
        "maxResults": max_results,
        "safeSearch": "strict",
        "videoEmbeddable": "true",
        "videoSyndicated": "true",
        "relevanceLanguage": "en",
    }

    try:
        response = requests.get(YOUTUBE_URL, params=params, timeout=4)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return []

    videos = []
    for item in data.get("items", []):
        try:
            snippet = item["snippet"]
            thumbs = snippet.get("thumbnails", {})
            videos.append({
                "video_id": item["id"]["videoId"],
                "title": snippet["title"],
                "description": snippet.get("description", ""),
                "thumbnail": (
                    thumbs.get("high", {}).get("url")
                    or thumbs.get("medium", {}).get("url")
                    or thumbs.get("default", {}).get("url", "")
                ),
            })
        except (KeyError, TypeError):
            continue

    cache.set(cache_key, videos, timeout=600)
    return videos