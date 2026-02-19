import os
import sys
import subprocess
import logging
from pathlib import Path

# Add root to sys.path to allow imports if needed, though we use subprocess
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

try:
    from db_scripts.db_helpers import count_undownloaded_videos
except ImportError:
    # Fallback if structure is tricky
    def count_undownloaded_videos():
        logger.error("Could not import db_helpers. Check PYTHONPATH.")
        return 0

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("workflow_runner.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("WorkflowRunner")

# Relative paths from project root
EDITED_CLIPS_DIR = Path(BASE_DIR) / "edited_clips"

def run_command(command, env_updates=None):
    """Run a python script as a subprocess."""
    env = os.environ.copy()
    if env_updates:
        env.update(env_updates)
    
    # Ensure root is in PYTHONPATH for the subprocesses
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{BASE_DIR}:{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = BASE_DIR

    logger.info(f"🚀 Executing: {' '.join(command)}")
    process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    # Stream output to logger
    for line in process.stdout:
        logger.info(f"  [Output] {line.strip()}")
    
    process.wait()
    if process.returncode != 0:
        logger.error(f"❌ Command failed with return code {process.returncode}")
        return False
    return True

def has_ready_clips():
    """Check if there are any .mp4 files in edited_clips that aren't in 'uploaded'."""
    if not EDITED_CLIPS_DIR.exists():
        return False
    clips = [f for f in os.listdir(EDITED_CLIPS_DIR) if f.endswith('.mp4')]
    return len(clips) > 0

def main():
    logger.info("============================================================")
    logger.info("🤖 Master Workflow Runner Starting")
    logger.info("============================================================")

    # 1. If there are clips ready to publish, publish one, then stop
    if has_ready_clips():
        logger.info("✨ Found ready-to-publish clips. Starting uploader...")
        if run_command(["python3", "uploader/uploader.py"]):
            logger.info("✅ Single upload task finished. stopping.")
        else:
            logger.error("Failed to upload the existing clip.")
        return

    # 2. Check undownloaded videos in DB
    try:
        undownloaded_count = count_undownloaded_videos()
    except Exception as e:
        logger.error(f"Failed to check database: {e}")
        return

    if undownloaded_count == 0:
        # 3. No videos left, run scraper to find new ones
        logger.info("🔍 No undownloaded videos in DB. Running scraper...")
        # LinkScraper uses MAX_VIDEOS_PER_CHANNEL env var as updated
        if run_command(["python3", "scraper/LinkScraper.py"], {"MAX_VIDEOS_PER_CHANNEL": "2"}):
            undownloaded_count = count_undownloaded_videos()
            if undownloaded_count == 0:
                logger.info("📭 No new videos found even after scraping. Exiting.")
                return
            logger.info(f"📥 Found {undownloaded_count} new videos after scraping.")
        else:
            logger.error("Scraper failed.")
            return

    # Full Pipeline
    logger.info("⚙️ Starting full pipeline (Download -> Transcribe -> Highlight -> Clip -> Edit -> Upload)...")
    
    pipeline = [
        ["python3", "downloader/Downloader.py"],
        ["python3", "transcriber/Transcriber.py"],
        ["python3", "highlighter/HighlightFinder.py"],
        ["python3", "clipper/ClipGenerator.py"],
        ["python3", "editor/VideoEditor.py"],
        ["python3", "uploader/uploader.py"]
    ]

    for cmd in pipeline:
        # We run the command relative to BASE_DIR
        cmd[1] = os.path.join(BASE_DIR, cmd[1])
        if not run_command(cmd):
            logger.error(f"💀 Pipeline BROKE at step: {' '.join(cmd)}")
            return

    logger.info("🎯 Workflow completed successfully. one full video processed and uploaded.")

if __name__ == "__main__":
    main()
