import os
import json
import subprocess
from pathlib import Path
from faster_whisper import WhisperModel
import logging
import time

# Constants
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IS_DOCKER = os.path.exists("/.dockerenv")

DOWNLOAD_DIR = "/downloads" if IS_DOCKER else os.path.join(BASE_DIR, "downloads")
TRANSCRIPT_DIR = "/transcripts" if IS_DOCKER else os.path.join(BASE_DIR, "transcripts")
SIMPLE_TRANSCRIPT_DIR = "/transcripts_simple" if IS_DOCKER else os.path.join(BASE_DIR, "transcripts_simple")

os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
os.makedirs(SIMPLE_TRANSCRIPT_DIR, exist_ok=True)

logger = logging.getLogger("Transcriber")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/app/transcriber.log" if IS_DOCKER else os.path.join(BASE_DIR, "transcriber.log"))
    ]
)

# Load Faster-Whisper model
# Efficiency: Faster-Whisper is much faster than standard Whisper
# Accuracy: Using word-level timestamps instead of linear interpolation
MODEL_SIZE = "small" # options: "tiny", "base", "small", "medium", "large-v3"
logger.info(f"Loading Faster-Whisper model: {MODEL_SIZE}")

# Use "float32" for CPU if "int8" is not supported, or "int8" for best efficiency on CPU
model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

def extract_audio(video_path):
    """Extract normalized audio from video as WAV."""
    audio_path = video_path.with_suffix(".wav")
    logger.info(f"Extracting audio from {video_path.name}...")
    
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(video_path),
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        "-af", "volume=1.5",
        "-y",
        str(audio_path)
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if not audio_path.exists() or audio_path.stat().st_size == 0:
            raise RuntimeError("FFmpeg output file is empty")
        return audio_path
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg failed: {e.stderr.decode()}")
        return None
    except Exception as e:
        logger.error(f"Audio extraction error: {e}")
        return None

def transcribe_audio(audio_path):
    """Transcribe audio using Faster-Whisper with word-level timestamps."""
    if not audio_path:
        return None

    try:
        start_time = time.time()
        # Efficiency: word_timestamps=True provides exact word timing
        segments, info = model.transcribe(
            str(audio_path),
            beam_size=5,
            word_timestamps=True,
            language="en" # Force English if known, or set to None for auto
        )
        
        logger.info(f"Transcription language: {info.language} ({info.language_probability:.2f})")
        
        results = {
            "text": "",
            "segments": [],
            "words": []
        }

        for segment in segments:
            seg_data = {
                "start": round(segment.start, 3),
                "end": round(segment.end, 3),
                "text": segment.text.strip()
            }
            results["segments"].append(seg_data)
            results["text"] += segment.text + " "
            
            if segment.words:
                for word in segment.words:
                    results["words"].append({
                        "start": round(word.start, 3),
                        "end": round(word.end, 3),
                        "word": word.word.strip(),
                        "probability": word.probability
                    })

        duration = time.time() - start_time
        logger.info(f"Transcription finished in {duration:.2f}s")
        return results
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return None

def get_simplified_transcript(whisper_result, max_words=2):
    """
    Generate simplified transcript using EXACT word timestamps.
    Chunks words into groups of `max_words`.
    """
    if not whisper_result or not whisper_result.get("words"):
        return []

    words = whisper_result["words"]
    simplified = []
    
    for i in range(0, len(words), max_words):
        chunk = words[i:i + max_words]
        if not chunk:
            continue
            
        simplified.append({
            "start": chunk[0]["start"],
            "end": chunk[-1]["end"],
            "text": " ".join([w["word"] for w in chunk]),
            "confidence": round(sum([w["probability"] for w in chunk]) / len(chunk), 3)
        })

    return simplified

def save_json(data, output_path):
    """Safely save data to JSON."""
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved: {output_path.name}")
    except Exception as e:
        logger.error(f"Failed to save {output_path}: {e}")

def main():
    logger.info("Starting Transcriber Service")
    videos = list(Path(DOWNLOAD_DIR).glob("*.mp4"))
    
    if not videos:
        logger.info("No videos found to process.")
        return

    for video_path in videos:
        # Check if already transcribed to avoid redundant work
        simple_path = Path(SIMPLE_TRANSCRIPT_DIR) / f"{video_path.stem}_simple.json"
        if simple_path.exists():
            logger.info(f"Skipping {video_path.name} (already transcribed)")
            continue

        audio_path = extract_audio(video_path)
        if not audio_path:
            continue

        logger.info(f"Transcribing {video_path.name}...")
        result = transcribe_audio(audio_path)
        
        if result:
            # Save full transcript
            full_path = Path(TRANSCRIPT_DIR) / f"{video_path.stem}.json"
            save_json(result, full_path)

            # Save simplified (word-exact) transcript
            simplified = get_simplified_transcript(result)
            save_json(simplified, simple_path)

        # Cleanup audio
        if audio_path.exists():
            audio_path.unlink()

    logger.info("Transcriber Process Complete")

if __name__ == "__main__":
    main()
