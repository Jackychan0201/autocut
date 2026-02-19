import os
import json
import random
import subprocess
import logging
import re
from pathlib import Path
from datetime import timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("VideoEditor")

# Directories and Files
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IS_DOCKER = os.path.exists("/.dockerenv")

# Robust FFmpeg Path handling
NODE_FFMPEG = os.path.join(BASE_DIR, "node_modules", "@ffmpeg-installer", "darwin-arm64", "ffmpeg")
if not IS_DOCKER and os.path.exists(NODE_FFMPEG):
    FFMPEG_PATH = NODE_FFMPEG
else:
    FFMPEG_PATH = "ffmpeg"

FONTS_DIR = "/app/fonts" if IS_DOCKER else os.path.join(BASE_DIR, "editor", "fonts")
BG_VIDEOS_DIR = "/bg_videos" if IS_DOCKER else os.path.join(BASE_DIR, "editor", "bg_videos")
CLIPS_DIR = "/clips" if IS_DOCKER else os.path.join(BASE_DIR, "clips")
HIGHLIGHTS_DIR = "/highlights" if IS_DOCKER else os.path.join(BASE_DIR, "highlights")
TRANSCRIPTS_DIR = "/transcripts_simple" if IS_DOCKER else os.path.join(BASE_DIR, "transcripts_simple")
TRANSCRIPTS_FULL_DIR = "/transcripts" if IS_DOCKER else os.path.join(BASE_DIR, "transcripts")
DOWNLOADS_DIR = "/downloads" if IS_DOCKER else os.path.join(BASE_DIR, "downloads")
EDITED_DIR = "/edited_clips" if IS_DOCKER else os.path.join(BASE_DIR, "edited_clips")

os.makedirs(EDITED_DIR, exist_ok=True)

# Styles
FONT_NAME = "Futura Heavy"
FONT_SIZE = 110
HIGHLIGHT_COLOR = "&H0000E6FF"  # Targeted Viral Yellow

def format_timestamp(seconds):
    """Convert seconds to ASS timestamp format (H:MM:SS.cc)"""
    td = timedelta(seconds=seconds)
    total_seconds = max(0, td.total_seconds())
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    secs = total_seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"

def get_word_level_captions(clip_name, full_transcript, highlights):
    """Extract exact word timings for a specific clip."""
    match = re.search(r"clip_(\d+)", clip_name)
    if not match: return []
    
    idx = int(match.group(1)) - 1
    if idx < 0 or idx >= len(highlights): return []
    
    highlight = highlights[idx]
    start_time = highlight['start']
    end_time = highlight['end']
    
    clip_words = []
    for seg in full_transcript:
        if seg['start'] >= start_time and seg['end'] <= end_time:
            word_seg = seg.copy()
            word_seg['start'] = max(0, seg['start'] - start_time)
            word_seg['end'] = max(0, seg['end'] - start_time)
            clip_words.append(word_seg)
    return clip_words

def generate_ass_file(clip_name, word_segments):
    """Create a high-end subtitle file with pop animations."""
    ass_path = Path(EDITED_DIR) / f"{clip_name}.ass"
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{FONT_NAME},{FONT_SIZE},&H00FFFFFF,{HIGHLIGHT_COLOR},&H00000000,&H00000000,1,0,0,0,100,100,2,0,1,10,4,2,10,10,500,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    dialogues = []
    for word in word_segments:
        start = format_timestamp(word['start'])
        end = format_timestamp(word['end'])
        clean_text = word['text'].strip().upper()
        # Pop Animation: Growing 100 -> 125 -> 100
        text = f"{{\\c{HIGHLIGHT_COLOR}\\fscx100\\fscy100\\t(0,100,\\fscx125\\fscy125)\\t(100,200,\\fscx100\\fscy100)}}{clean_text}"
        dialogues.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")
        
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(dialogues))
    return ass_path

def get_random_bg_video():
    bg_path = Path(BG_VIDEOS_DIR)
    videos = list(bg_path.glob("*.mp4")) + list(bg_path.glob("*.mov"))
    return random.choice(videos) if videos else None

def apply_pro_edits(clip_path, highlights, full_transcript):
    clip_name = clip_path.stem
    output_path = Path(EDITED_DIR) / f"{clip_name}_viral.mp4"
    
    if output_path.exists():
        logger.info(f"⏭️  Skipping {clip_name} (already edited)")
        return

    word_segments = get_word_level_captions(clip_name, full_transcript, highlights)
    if not word_segments:
        logger.warning(f"⚠️ No transcript found for {clip_name}. Copying raw.")
        subprocess.run([FFMPEG_PATH, "-i", str(clip_path), "-c", "copy", str(output_path), "-y"], check=True)
        return

    ass_path = generate_ass_file(clip_name, word_segments)
    bg_video = get_random_bg_video()
    
    # Path escaping for FFmpeg (macOS/Unix)
    safe_ass_path = str(ass_path).replace(":", "\\:").replace("'", "\\'")
    safe_fonts_dir = str(FONTS_DIR).replace(":", "\\:").replace("'", "\\'")

    if bg_video:
        logger.info(f"🎬 Editing {clip_name} (Top 1/3: Main, Bottom 2/3: Gameplay)...")
        filter_complex = (
            "[0:v]scale=720:1440:force_original_aspect_ratio=decrease,"
            "pad=720:1280:(ow-iw)/2:(oh-ih)/2[main];"
            "[1:v]scale=720:-2:force_original_aspect_ratio=decrease,"
            "crop=720:853,format=rgba[bg];"
            f"[main][bg]overlay=0:426:shortest=1,ass=filename='{safe_ass_path}':fontsdir='{safe_fonts_dir}'"
        )
        cmd = [
            FFMPEG_PATH, "-hide_banner", "-loglevel", "error",
            "-i", str(clip_path), "-stream_loop", "-1", "-i", str(bg_video),
            "-filter_complex", filter_complex,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-map", "0:a", "-shortest", "-movflags", "+faststart", "-y", str(output_path)
        ]
    else:
        logger.info(f"🎬 Editing {clip_name} (No BG found, falling back to blur)...")
        filter_complex = (
            "[0:v]scale=720:1440:force_original_aspect_ratio=decrease,"
            "pad=720:1280:(ow-iw)/2:(oh-ih)/2[main];"
            "[0:v]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,boxblur=20:10[bg];"
            f"[bg][main]overlay=0:0,ass=filename='{safe_ass_path}':fontsdir='{safe_fonts_dir}'"
        )
        cmd = [
            FFMPEG_PATH, "-hide_banner", "-loglevel", "error",
            "-i", str(clip_path), "-filter_complex", filter_complex,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "copy", "-movflags", "+faststart", "-y", str(output_path)
        ]

    try:
        subprocess.run(cmd, check=True)
        logger.info(f"✨ Edited: {output_path.name}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Edit failed for clip {clip_name}: {e}")
        return False
    finally:
        if ass_path.exists():
            ass_path.unlink()

def cleanup(h_file_path):
    video_stem = h_file_path.stem.replace("_simple_highlights", "").replace("_highlights", "")
    logger.info(f"🧹 Starting cleanup for: {video_stem}")
    
    # 1. Delete original download
    for ext in [".mp4", ".mkv", ".mov", ".webm"]:
        video_path = Path(DOWNLOADS_DIR) / f"{video_stem}{ext}"
        if video_path.exists():
            video_path.unlink()
            logger.info(f"Removed download: {video_path.name}")

    # 2. Delete transcripts
    t_full = Path(TRANSCRIPTS_FULL_DIR) / f"{video_stem}.json"
    if t_full.exists():
        t_full.unlink()
        logger.info(f"Removed full transcript: {t_full.name}")
        
    t_simple = Path(TRANSCRIPTS_DIR) / f"{video_stem}_simple.json"
    if t_simple.exists():
        t_simple.unlink()
        logger.info(f"Removed simple transcript: {t_simple.name}")

    # 3. Delete raw clips
    for clip in Path(CLIPS_DIR).glob("clip_*.mp4"):
        clip.unlink()
        logger.info(f"Removed raw clip: {clip.name}")

def main():
    logger.info("============================================================")
    logger.info("🎨 Viral Video Editor Starting")
    logger.info(f"🔨 Using FFmpeg: {FFMPEG_PATH}")
    logger.info("============================================================")
    
    h_files = list(Path(HIGHLIGHTS_DIR).glob("*_highlights.json"))
    if not h_files:
        logger.info("No highlights found.")
        return
        
    global_success = True
    processed_any = False
    
    for h_file in h_files:
        video_stem = h_file.stem.replace("_simple_highlights", "").replace("_highlights", "")
        t_file = Path(TRANSCRIPTS_DIR) / f"{video_stem}_simple.json"
        
        if not t_file.exists():
            logger.warning(f"⏩ Skipping {h_file.name} - Transcript missing for {video_stem}")
            continue

        logger.info(f"📦 Processing Video: {video_stem}")
        with open(h_file, "r", encoding="utf-8") as f:
            highlights = json.load(f)
        with open(t_file, "r", encoding="utf-8") as f:
            transcript = json.load(f)

        clips = list(Path(CLIPS_DIR).glob("clip_*.mp4"))
        if not clips:
            logger.info(f"No clips found for {video_stem}. Run Clipper first.")
            continue

        clips.sort(key=lambda x: int(re.search(r"(\d+)", x.name).group(1)))

        video_success = True
        for clip in clips:
            if not apply_pro_edits(clip, highlights, transcript):
                video_success = False
                global_success = False

        if video_success:
            cleanup(h_file)
            processed_any = True
        else:
            logger.error(f"❌ Skipping cleanup for {video_stem} due to edit failures.")

    if not processed_any and not global_success:
        logger.error("💀 Editor failed to process any videos successfully.")
        sys.exit(1)
    
    if processed_any:
        logger.info("✅ Editor Process Complete.")
    else:
        logger.info("📭 No videos were eligible for editing.")

if __name__ == "__main__":
    import sys
    main()
