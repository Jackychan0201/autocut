# downloader/downloader.py
import os
import logging
import yt_dlp

from db_scripts.db_connect import db_conn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Downloader")

# Constants
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOWNLOAD_DIR = "/downloads" if os.path.exists("/.dockerenv") else os.path.join(BASE_DIR, "downloads")

def fetch_next_video():
    """Fetch one video that is not downloaded yet."""
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, link FROM Videos WHERE is_downloaded = FALSE LIMIT 1;")
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row  # (id, link) or None

def mark_downloaded(video_id):
    """Mark video as downloaded."""
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("UPDATE Videos SET is_downloaded = TRUE WHERE id = %s;", (video_id,))
    conn.commit()
    cur.close()
    conn.close()

def download_highest_quality(video_id, video_url):
    """Download best video + audio and merge into one MP4."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    ydl_opts = {
    "format": "bv*+ba/b",  # safer fallback
    "outtmpl": f"{DOWNLOAD_DIR}/%(title)s [%(id)s].%(ext)s",
    "merge_output_format": "mp4",
    "noplaylist": True,
    "quiet": False,
    "http_headers": {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    },
    "extractor_args": {
        "youtube": {
            "player_client": ["android"]  
        }
    },
    "postprocessors": [
        {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}
    ],
    "progress_hooks": [lambda d: progress_hook(d, video_id)],
}


    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
    except Exception as e:
        logger.error(f"Download failed for {video_url}: {e}")

def progress_hook(d, video_id):
    """Hook to update progress or mark as downloaded."""
    if d["status"] == "finished":
        logger.info(f"✅ Finished downloading: {d['filename']}")
        mark_downloaded(video_id)

def main():
    video = fetch_next_video()
    if not video:
        logger.info("No videos left to download.")
        return

    video_id, video_url = video
    logger.info(f"🎬 Starting download: {video_url}")
    download_highest_quality(video_id, video_url)

if __name__ == "__main__":
    main()
