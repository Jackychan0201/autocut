import os
import json
import subprocess
import logging
import re
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("ClipGenerator")

# Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IS_DOCKER = os.path.exists("/.dockerenv")

DOWNLOADS_DIR = "/downloads" if IS_DOCKER else os.path.join(BASE_DIR, "downloads")
HIGHLIGHTS_DIR = "/highlights" if IS_DOCKER else os.path.join(BASE_DIR, "highlights")
CLIPS_DIR = "/clips" if IS_DOCKER else os.path.join(BASE_DIR, "clips")

os.makedirs(CLIPS_DIR, exist_ok=True)

def load_all_highlights():
    """Load all highlights JSON files from the highlights directory."""
    return list(Path(HIGHLIGHTS_DIR).glob("*_highlights.json"))

def sanitize_filename(name: str) -> str:
    """Sanitize title to make it safe for filenames."""
    # Remove disallowed characters and collapse spaces/underscores
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s-]+", "_", name)
    # Ensure it's not too long and lowercase for consistency
    return name.strip("_").lower()[:50]

def get_video_path(video_stem):
    """Find matching video file in /downloads."""
    for ext in [".mp4", ".mkv", ".mov", ".webm"]:
        path = Path(DOWNLOADS_DIR) / f"{video_stem}{ext}"
        if path.exists():
            return path
    return None

def create_clip(video_path, start, end, output_path):
    """
    Extract a clip and format it for 9:16 vertical video.
    Efficiency: Uses fast-seek (-ss before -i) and hardware-friendly settings.
    Accuracy: Re-encoding ensures frame-accurate cuts.
    """
    if output_path.exists():
        logger.info(f"⏭️  Skipping existing clip: {output_path.name}")
        return True

    duration = end - start
    # Layout: Original horizontal video in the top third of a 9:16 frame
    # 1. Scale video to 1080 width (standard TikTok/Shorts width)
    # 2. Pad to 1080x1920, placing the video at the very top (y=0)
    vf_filter = (
        "scale=1080:-1,"       # Scale to 1080 width, maintain aspect ratio
        "pad=1080:1920:0:0:black" # Container 1080x1920, video at top, remainder black
    )

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-ss", str(max(0, start - 0.5)), # Accurate seek (slight buffer)
        "-i", str(video_path),
        "-ss", "0.5",                    # Precise seek within the cut
        "-t", str(duration),
        "-vf", vf_filter,
        "-c:v", "libx264", 
        "-preset", "veryfast",           # Efficiency: faster encoding
        "-crf", "22",                    # Good balance of size/quality
        "-c:a", "aac", "-b:a", "192k",
        "-y", str(output_path)
    ]

    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ FFmpeg failed for {output_path.name}: {e}")
        return False

def process_highlight_file(file_path):
    """Process a single highlights JSON file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            highlights = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read {file_path}: {e}")
        return

    # Determine original video name from JSON filename
    video_stem = file_path.stem.replace("_simple_highlights", "").replace("_highlights", "")
    video_path = get_video_path(video_stem)
    
    if not video_path:
        logger.error(f"Could not find source video for {file_path.name}")
        return

    logger.info(f"🎞️  Processing {len(highlights)} clips for: {video_path.name}")
    
    for i, h in enumerate(highlights):
        start = h.get("start")
        end = h.get("end")
        title = h.get("title", f"clip_{i+1}")
        
        if start is None or end is None:
            continue

        output_name = f"clip_{i+1:02d}.mp4"
        output_path = Path(CLIPS_DIR) / output_name

        if create_clip(video_path, start, end, output_path):
            logger.info(f"✅ Created: {output_name}")

def main():
    logger.info("============================================================")
    logger.info("✂️  Viral Clip Generator Starting")
    logger.info("============================================================")
    
    highlight_files = load_all_highlights()
    if not highlight_files:
        logger.info("No highlights to process. Run Highlighter first.")
        return

    for h_file in highlight_files:
        process_highlight_file(h_file)

    logger.info("🎬 All highlights processed successfully.")

if __name__ == "__main__":
    main()
