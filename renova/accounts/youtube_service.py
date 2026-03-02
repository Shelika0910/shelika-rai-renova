import requests
from django.conf import settings


def get_youtube_videos(query="motivational videos", max_results=6):
    """
    Fetch YouTube videos using the YouTube Data API v3.
    
    Args:
        query: Search query string
        max_results: Maximum number of videos to return
        
    Returns:
        List of video dictionaries with title, description, video_id, thumbnail
        Returns empty list on any failure
    """
    try:
        # Validate API key exists
        api_key = str(settings.YOUTUBE_API_KEY).strip()
        if not api_key:
            print("YouTube API Error: API key not configured")
            return []

        url = "https://www.googleapis.com/youtube/v3/search"

        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": max_results,
            "key": api_key,
            "safeSearch": "strict",
            "videoEmbeddable": "true",
            "videoSyndicated": "true",
        }

        response = requests.get(url, params=params, timeout=15)
        
        # Check HTTP status code
        if response.status_code != 200:
            print(f"YouTube API HTTP Error: Status {response.status_code}")
            print(f"Response: {response.text}")
            return []
        
        # Raise exception for bad status codes
        response.raise_for_status()
        
        data = response.json()

        # Check for API-level errors
        if "error" in data:
            error_info = data["error"]
            print(f"YouTube API Error Code: {error_info.get('code', 'Unknown')}")
            print(f"YouTube API Error Message: {error_info.get('message', 'No message')}")
            if "errors" in error_info:
                for err in error_info["errors"]:
                    print(f"  - {err.get('reason', 'Unknown reason')}: {err.get('message', '')}")
            return []

        # Parse video items
        videos = []
        items = data.get("items", [])
        
        if not items:
            print(f"YouTube API: No videos found for query '{query}'")
            return []

        for item in items:
            try:
                video_data = {
                    "title": item["snippet"]["title"],
                    "description": item["snippet"]["description"],
                    "video_id": item["id"]["videoId"],
                    "thumbnail": item["snippet"]["thumbnails"]["medium"]["url"],
                }
                videos.append(video_data)
            except KeyError as e:
                print(f"YouTube API: Skipping video due to missing field: {e}")
                continue

        return videos

    except requests.exceptions.Timeout:
        print("YouTube API Error: Request timed out")
        return []
    except requests.exceptions.ConnectionError:
        print("YouTube API Error: Connection failed")
        return []
    except requests.exceptions.HTTPError as e:
        print(f"YouTube API HTTP Error: {e}")
        return []
    except requests.exceptions.RequestException as e:
        print(f"YouTube API Request Error: {e}")
        return []
    except ValueError as e:
        print(f"YouTube API JSON Parse Error: {e}")
        return []
    except Exception as e:
        print(f"YouTube API Unexpected Error: {type(e).__name__}: {e}")
        return []
