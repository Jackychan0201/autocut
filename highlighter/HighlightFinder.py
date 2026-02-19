import os
import json
import logging
import re
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("HighlightFinder")

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IS_DOCKER = os.path.exists("/.dockerenv")

TRANSCRIPT_SIMPLE_DIR = "/transcripts_simple" if IS_DOCKER else os.path.join(BASE_DIR, "transcripts_simple")
HIGHLIGHTS_DIR = "/highlights" if IS_DOCKER else os.path.join(BASE_DIR, "highlights")
os.makedirs(HIGHLIGHTS_DIR, exist_ok=True)

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    logger.error("GEMINI_API_KEY not found in environment variables.")
genai.configure(api_key=api_key)

# ==================== MASTER PROMPT ====================
HIGHLIGHT_MASTER_PROMPT = """You are an expert Social Media Content Strategist and Viral Growth Specialist.
Your mission is to analyze video transcripts and identify the most engaging, high-impact moments that will go viral on TikTok, Instagram Reels, and YouTube Shorts.

Your task is to identify the top 5-8 most viral moments from the provided timecoded transcript.

**VIRALITY CRITERIA:**
1. **Emotional Impact:** Moments that trigger laughter, shock, inspiration, or strong empathy.
2. **The "Hook":** Does the segment start with something that immediately grabs attention?
3. **Standalone Value:** Can a viewer understand and appreciate the clip without watching the whole video?
4. **Shareability:** Is it something a viewer would send to a friend or save for later?
5. **Insights/Wisdom:** Life-changing advice, "aha!" moments, or counter-intuitive facts.

**CONSTRAINTS:**
- **Duration:** Each highlight MUST be between 20 and 50 seconds.
- **Completion:** Do not cut mid-sentence or mid-thought. Ensure the segment has a clear beginning and end.
- **Non-Overlapping:** Highlights must not overlap in time.
- **Variety:** Select moments from different parts of the video (beginning, middle, end).

**OUTPUT FORMAT:**
Return ONLY a valid JSON array of objects with this exact structure:
[
  {
    "start": <float_seconds>,
    "end": <float_seconds>,
    "title": "<catchy_viral_title>",
    "summary": "<brief_explanation_of_viral_value>",
    "hashtags": ["#tag1", "#tag2", "#tag3"]
  }
]

**TITLE GUIDELINES:**
- Use catchy, click-baity (but accurate) titles (e.g., "The Secret to Infinite Energy", "She Couldn't Believe He Said This").
- Keep it under 10 words.
- Maximize curiosity.

Now, analyze the following timecoded transcript segments and find the viral gold:
"""

def load_transcript():
    """Load the first available simplified transcript."""
    files = list(Path(TRANSCRIPT_SIMPLE_DIR).glob("*.json"))
    if not files:
        logger.info("No simplified transcripts found in %s", TRANSCRIPT_SIMPLE_DIR)
        return None, None
    
    # Process the first one found (or we could loop if needed)
    file_path = files[0]
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            transcript = json.load(f)
        return transcript, file_path
    except Exception as e:
        logger.error("Failed to load transcript %s: %s", file_path, e)
        return None, None

def find_highlights(transcript, filename):
    """Use Gemini AI to find engaging or viral moments."""
    # Prepare transcript for Gemini (include timestamps this time!)
    # We'll format it as a string to stay within token limits if it's very long, 
    # but since it's "simple" (2 words/seg), it might be large.
    # We'll take every 5th segment if too long, or just pass as is for better accuracy.
    formatted_transcript = ""
    for seg in transcript:
        formatted_transcript += f"[{seg['start']:.2f} - {seg['end']:.2f}] {seg['text']}\n"

    prompt = HIGHLIGHT_MASTER_PROMPT + f"\nTRANSCRIPT FOR: {filename}\n\n" + formatted_transcript
    
    try:
        # Use gemini-2.5-flash for speed and reliability, supports long context
        model = genai.GenerativeModel("gemini-2.5-flash")
        logger.info("Sending transcript to Gemini (analyzing viral potential)...")
        response = model.generate_content(prompt)
        
        if not response or not response.text:
            logger.error("Gemini returned an empty response.")
            return []

        text = response.text.strip()
        # Clean up Markdown
        text = text.replace("```json", "").replace("```", "").strip()
        
        # Robust JSON extraction
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            json_text = match.group(0)
            highlights = json.loads(json_text)
            
            # Validate duration constraints locally
            validated = []
            for h in highlights:
                duration = h['end'] - h['start']
                if 18 <= duration <= 60: # Allow slight wiggle room for AI
                    validated.append(h)
                else:
                    logger.warning(f"Clip '{h['title']}' rejected due to duration: {duration:.1f}s")
            
            return validated
        else:
            logger.warning("No JSON array found in Gemini output.")
            return []

    except Exception as e:
        logger.error(f"AI Highlight detection failed for {filename}: {e}")
        return []

def main():
    logger.info("============================================================")
    logger.info("🚀 AI-Powered Viral Highlight Finder Starting")
    logger.info("============================================================")
    
    transcript, file_path = load_transcript()
    if not transcript:
        return

    # Check if highlights already exist
    out_path = Path(HIGHLIGHTS_DIR) / f"{file_path.stem}_highlights.json"
    if out_path.exists():
        logger.info(f"✅ Highlights already exist for {file_path.name}")
        # Optionally load and return them for debug
        with open(out_path, "r", encoding="utf-8") as f:
            return json.load(f)

    logger.info(f"🔍 Analyzing video: {file_path.name}")
    highlights = find_highlights(transcript, file_path.name)
    
    if highlights:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(highlights, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ Found {len(highlights)} viral moments!")
        logger.info(f"💾 Highlights saved to {out_path}")
    else:
        logger.warning(f"❌ No viral highlights identified for {file_path.name}")

    return highlights

if __name__ == "__main__":
    highlights = main()
    if highlights:
        # Print a nice summary
        print("\n" + "="*40)
        print("🎬 RECAP: POTENTIAL VIRAL HITS")
        print("="*40)
        for i, h in enumerate(highlights, 1):
            dur = h['end'] - h['start']
            print(f"{i}. [{dur:.1f}s] {h['title']}")
            print(f"   Reason: {h['summary'][:100]}...")
        print("="*40 + "\n")
