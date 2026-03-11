import requests
from django.conf import settings


def get_youtube_videos(query="mental health wellness", max_results=6):
    """
    Fetch YouTube videos via the YouTube Data API v3.
    Returns a list of dicts: {title, description, video_id, thumbnail}
    Returns [] on any error.
    """
    try:
        api_key = str(settings.YOUTUBE_API_KEY).strip()
        if not api_key:
            print("YouTube API: No API key configured.")
            return []

        response = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": max_results,
                "key": api_key,
                "safeSearch": "strict",
                "videoEmbeddable": "true",
                "videoSyndicated": "true",
                "relevanceLanguage": "en",
            },
            timeout=10,
        )

        if response.status_code != 200:
            print(f"YouTube API HTTP {response.status_code}: {response.text[:400]}")
            return []

        data = response.json()

        if "error" in data:
            err = data["error"]
            print(f"YouTube API error {err.get('code')}: {err.get('message')}")
            return []

        videos = []
        for item in data.get("items", []):
            try:
                videos.append({
                    "title": item["snippet"]["title"],
                    "description": item["snippet"]["description"],
                    "video_id": item["id"]["videoId"],
                    "thumbnail": (
                        item["snippet"]["thumbnails"].get("medium", {}).get("url")
                        or item["snippet"]["thumbnails"].get("default", {}).get("url", "")
                    ),
                })
            except (KeyError, TypeError):
                continue

        return videos

    except requests.exceptions.Timeout:
        print("YouTube API: Request timed out.")
        return []
    except Exception as e:
        print(f"YouTube API error: {e}")
        return []
