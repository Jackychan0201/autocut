# LinkScraper.py
import os
import logging
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv
import requests
import isodate

import feedparser
from datetime import datetime, timedelta, timezone
import time
from db_scripts.db_insert import db_insert_video
from db_scripts.db_helpers import fetch_channels, video_exists

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("LinkScraper")

YT_API_SEARCH = "https://www.googleapis.com/youtube/v3/search"
YT_API_CHANNELS = "https://youtube.googleapis.com/youtube/v3/channels"
YT_API_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"

MIN_DURATION_MIN = 10  # only videos longer than 15 minutes
MAX_DURATION_MIN = 20 # only videos shorter than 120 minutes
MAX_AGE_DAYS = 7       # only videos published in the last 7 days

# ----------------- Helper Functions ----------------- #

def extract_youtube_id_from_url(url):
    """Parse a YouTube link and extract ID + type (channel, user, video, handle)."""
    try:
        p = urlparse(url)
        path = p.path or ""
        if "youtube.com" not in p.netloc and "youtu.be" not in p.netloc:
            return (None, None)

        if p.netloc.endswith("youtu.be"):
            return ("video", path.lstrip("/"))

        parts = path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "channel":
            return ("channel", parts[1])
        if len(parts) >= 2 and parts[0] == "user":
            return ("user", parts[1])
        if parts and parts[0] == "watch":
            q = parse_qs(p.query)
            if "v" in q:
                return ("video", q["v"][0])
        if parts and parts[0].startswith("@"):
            return ("handle", parts[0][1:])
    except Exception:
        pass
    return (None, None)


def fetch_videos_via_rss(channel_id):
    """Fetch recent videos using RSS feed (0 quota cost) filtered by age."""
    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    try:
        feed = feedparser.parse(rss_url)
        video_ids = []
        now = time.time()
        max_age_seconds = MAX_AGE_DAYS * 24 * 60 * 60
        
        for entry in feed.entries:
            # Check publication date
            if hasattr(entry, 'published_parsed'):
                pub_time = time.mktime(entry.published_parsed)
                if now - pub_time > max_age_seconds:
                    continue # Skip older videos
            
            # Entry ID is usually yt:video:VIDEO_ID
            v_id = entry.yt_videoid if hasattr(entry, 'yt_videoid') else entry.id.split(':')[-1]
            video_ids.append(v_id)
        return video_ids
    except Exception as e:
        logger.warning(f"RSS fetch failed for {channel_id}: {e}")
        return []

def get_video_details(video_ids, min_duration_min=15, max_duration_min=120):
    """Batch fetch video details and filter by duration (1 unit per 50 videos)."""
    api_key = os.getenv("YT_API_KEY")
    if not api_key or not video_ids:
        return []

    # Prepare IDs in blocks of 50
    params_v = {
        "part": "contentDetails",
        "id": ",".join(video_ids[:50]),
        "key": api_key
    }
    
    try:
        r = requests.get(YT_API_VIDEOS, params=params_v, timeout=10)
        if r.status_code == 403:
            logger.error(f"Forbidden (403) for videos.list: {r.text}")
        r.raise_for_status()
        
        videos_data = r.json().get("items", [])
        
        def parse_duration(iso_duration):
            return int(isodate.parse_duration(iso_duration).total_seconds())

        filtered_videos = [
            f"https://www.youtube.com/watch?v={v['id']}"
            for v in videos_data
            if min_duration_min * 60 <= parse_duration(v["contentDetails"]["duration"]) <= max_duration_min * 60
        ]
        return filtered_videos
    except Exception as e:
        logger.warning(f"Failed to fetch video details: {e}")
        return []

def fetch_videos_with_youtube_api(identifier, id_type="channelId", max_results=50, min_duration_min=15, max_duration_min=120):
    """Fetch videos via YouTube Data API (100 units cost - BACKUP ONLY)."""
    api_key = os.getenv("YT_API_KEY")
    if not api_key:
        raise RuntimeError("YT_API_KEY not set for YouTube Data API calls")

    # Calculate publishedAfter date
    published_after = (datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)).isoformat()

    # Step 1: Get video IDs from search
    params = {
        "part": "id",
        "order": "date",
        "maxResults": str(min(50, max_results)),
        "type": "video",
        "key": api_key,
        "publishedAfter": published_after,
    }
    if id_type == "channelId":
        params["channelId"] = identifier
    elif id_type == "forUsername":
        params["forUsername"] = identifier

    try:
        r = requests.get(YT_API_SEARCH, params=params, timeout=10)
        if r.status_code == 403:
            logger.error(f"Forbidden (403) for search.list: {r.text}")
        r.raise_for_status()
        data = r.json()
        video_ids = [i["id"]["videoId"] for i in data.get("items", []) if i["id"].get("videoId")]
        if not video_ids:
            return []
        
        return get_video_details(video_ids, min_duration_min, max_duration_min)
    except Exception as e:
        logger.warning(f"Search API failed: {e}")
        return []


def resolve_handle_to_channel_id(handle):
    """Convert a @handle into a channel ID."""
    api_key = os.getenv("YT_API_KEY")
    if not api_key:
        return None
    try:
        handle_name = handle.lstrip("@")
        params = {"part": "id", "forUsername": handle_name, "key": api_key}
        r = requests.get(YT_API_CHANNELS, params=params, timeout=10)
        r.raise_for_status()
        items = r.json().get("items", [])
        return items[0]["id"] if items else None
    except Exception as e:
        logger.warning(f"Failed to resolve handle '{handle}': {e}")
        return None


def get_videos_for_channel_link(link):
    """Return video links for a given channel link."""
    mode, identifier = extract_youtube_id_from_url(link)
    if not identifier:
        logger.warning(f"Could not determine ID from link: {link}")
        return []

    try:
        if mode == "channel":
            # TRY RSS FIRST (0 quota)
            v_ids = fetch_videos_via_rss(identifier)
            if v_ids:
                return get_video_details(v_ids, max_duration_min=MAX_DURATION_MIN)
            # Fallback to API if RSS fails
            return fetch_videos_with_youtube_api(identifier, id_type="channelId", max_duration_min=MAX_DURATION_MIN)
        
        if mode == "user":
            return fetch_videos_with_youtube_api(identifier, id_type="forUsername", max_duration_min=MAX_DURATION_MIN)
        
        if mode == "video":
            return [f"https://www.youtube.com/watch?v={identifier}"]
        
        if mode == "handle":
            channel_id = resolve_handle_to_channel_id(identifier)
            if channel_id:
                # TRY RSS FIRST (0 quota)
                v_ids = fetch_videos_via_rss(channel_id)
                if v_ids:
                    return get_video_details(v_ids, max_duration_min=MAX_DURATION_MIN)
                return fetch_videos_with_youtube_api(channel_id, id_type="channelId", max_duration_min=MAX_DURATION_MIN)
    except Exception as e:
        logger.warning(f"Error for {mode} '{identifier}': {e}")
    return []


# ----------------- Main Logic ----------------- #

def process_channel(channel_id, channel_name, channel_link, max_videos=None):
    logger.info(f"Processing channel '{channel_name}' (ID: {channel_id})")
    video_links = get_videos_for_channel_link(channel_link)
    if not video_links:
        logger.info(f"No videos found for {channel_name}")
        return

    added_count = 0
    for vlink in video_links:
        if max_videos is not None and added_count >= max_videos:
            logger.info(f"Reached limit of {max_videos} videos for {channel_name}")
            break
            
        if not video_exists(vlink):
            logger.info(f"Adding new video: {vlink}")
            db_insert_video(vlink, channel_id)
            added_count += 1


def main(max_videos_per_channel=None):
    channels = fetch_channels()
    if not channels:
        logger.info("No channels found. Please add channels and re-run.")
        return

    for ch_id, name, link in channels:
        try:
            process_channel(ch_id, name, link, max_videos=max_videos_per_channel)
        except Exception as e:
            logger.exception(f"Error processing channel {name}: {e}")


if __name__ == "__main__":
    # If run standalone, we might want to pass a limit from env or just no limit
    limit = int(os.getenv("MAX_VIDEOS_PER_CHANNEL", "0"))
    main(max_videos_per_channel=limit if limit > 0 else None)
