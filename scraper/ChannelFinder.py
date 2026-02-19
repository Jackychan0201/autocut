import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from googleapiclient.discovery import build
import google.generativeai as genai
import logging

# Setup paths
project_root = Path(__file__).resolve().parent.parent
relative_path = project_root / 'db_scripts'
sys.path.append(str(relative_path))

from db_scripts.db_insert import db_insert_channel

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ChannelFinder")

# Load environment variables
load_dotenv()
API_KEY = os.getenv("YT_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize APIs
YOUTUBE = build("youtube", "v3", developerKey=API_KEY)
genai.configure(api_key=GEMINI_API_KEY)

# ==================== MASTER PROMPT ====================
MASTER_PROMPT = """You are an expert YouTube content analyst specializing in identifying viral, high-quality channels.

Your mission: Analyze YouTube channels and determine if they are suitable for creating viral short-form content (TikTok, Reels, Shorts).

**TARGET CONTENT CATEGORIES:**
1. **Interviews** - Celebrity interviews, expert conversations, thought-provoking discussions
2. **Self-Education** - Personal development, skill-building, life advice, productivity
3. **Podcasts** - Long-form conversations, storytelling, deep-dive discussions

**EVALUATION CRITERIA:**

**VIRALITY POTENTIAL (40 points):**
- High engagement rate (views/subscribers ratio)
- Consistent viral moments (emotional, surprising, controversial)
- Quotable, shareable content
- Strong hooks and storytelling

**CONTENT QUALITY (30 points):**
- Professional production quality
- Compelling guests/topics
- Clear audio and video
- Engaging presentation style

**SHORT-FORM SUITABILITY (30 points):**
- Contains highlight-worthy moments
- Emotional peaks (laughter, shock, inspiration)
- Standalone insights that work out of context
- Visual interest (not just talking heads)

**SCORING SYSTEM:**
- 90-100: MUST ADD - Exceptional viral potential
- 70-89: HIGHLY RECOMMENDED - Strong candidate
- 50-69: CONSIDER - Decent potential
- Below 50: SKIP - Not suitable

**OUTPUT FORMAT:**
Return ONLY a valid JSON object with this structure:
{
  "score": <number 0-100>,
  "verdict": "<MUST ADD|HIGHLY RECOMMENDED|CONSIDER|SKIP>",
  "reasoning": "<2-3 sentence explanation>",
  "viral_potential": "<specific examples of viral moments>",
  "content_category": "<interviews|self-education|podcasts|mixed>",
  "recommended": <true|false>
}

**ANALYSIS GUIDELINES:**
- Be selective - only recommend channels with genuine viral potential
- Prioritize channels with proven track record of viral moments
- Consider if content translates well to 15-40 second clips
- Favor channels with emotional, surprising, or insightful content
- Reject channels that are too niche, boring, or low-quality

Now analyze the following channel:
"""

# ==================== CHANNEL DISCOVERY ====================

SEARCH_QUERIES = [
    # Reduced to 5 most effective queries to save API quota
    "viral podcast moments",
    "celebrity interview podcast",
    "self improvement podcast",
    "productivity tips channel",
    "trending podcast interviews",
]

def search_channels_by_query(query, max_results=5):  # Reduced from 10 to 5
    """Search for channels using YouTube API."""
    try:
        search_response = YOUTUBE.search().list(
            q=query,
            type="channel",
            part="id,snippet",
            maxResults=max_results,
            relevanceLanguage="en",
            regionCode="US",
            order="relevance"
        ).execute()
        
        return search_response.get("items", [])
    except Exception as e:
        logger.error(f"Search failed for query '{query}': {e}")
        return []

def get_channel_details(channel_id):
    """Get detailed channel information."""
    try:
        response = YOUTUBE.channels().list(
            part="snippet,statistics,contentDetails",
            id=channel_id
        ).execute()
        
        if not response.get("items"):
            return None
            
        channel = response["items"][0]
        snippet = channel["snippet"]
        stats = channel["statistics"]
        
        return {
            "id": channel_id,
            "title": snippet["title"],
            "description": snippet.get("description", "")[:500],  # Limit description length
            "subscriber_count": int(stats.get("subscriberCount", 0)),
            "video_count": int(stats.get("videoCount", 0)),
            "view_count": int(stats.get("viewCount", 0)),
            "country": snippet.get("country", "Unknown"),
            "url": f"https://youtube.com/channel/{channel_id}"
        }
    except Exception as e:
        logger.error(f"Failed to get details for channel {channel_id}: {e}")
        return None

def get_recent_videos(channel_id, max_results=5):
    """Get recent videos from a channel to analyze content."""
    try:
        search_response = YOUTUBE.search().list(
            channelId=channel_id,
            part="id,snippet",
            maxResults=max_results,
            order="date",
            type="video"
        ).execute()
        
        videos = []
        for item in search_response.get("items", []):
            videos.append({
                "title": item["snippet"]["title"],
                "description": item["snippet"].get("description", "")[:200]
            })
        
        return videos
    except Exception as e:
        logger.error(f"Failed to get videos for channel {channel_id}: {e}")
        return []

def analyze_channel_with_gemini(channel_info, recent_videos):
    """Use Gemini AI to analyze if channel is suitable."""
    
    # Prepare channel data for analysis
    channel_summary = f"""
CHANNEL: {channel_info['title']}
SUBSCRIBERS: {channel_info['subscriber_count']:,}
TOTAL VIEWS: {channel_info['view_count']:,}
VIDEO COUNT: {channel_info['video_count']}
COUNTRY: {channel_info['country']}

DESCRIPTION:
{channel_info['description']}

RECENT VIDEO TITLES:
"""
    
    for i, video in enumerate(recent_videos, 1):
        channel_summary += f"{i}. {video['title']}\n"
    
    # Call Gemini
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(MASTER_PROMPT + channel_summary)
        
        # Parse JSON response
        text = response.text.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        
        # Extract JSON
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            result = json.loads(match.group(0))
            return result
        else:
            logger.warning(f"No JSON found in Gemini response for {channel_info['title']}")
            return None
            
    except Exception as e:
        logger.error(f"Gemini analysis failed for {channel_info['title']}: {e}")
        return None

def find_viral_channels(min_score=70, max_channels=20):
    """Find viral channels using AI analysis."""
    logger.info("🔍 Starting AI-powered channel discovery...")
    
    all_channel_ids = set()
    recommended_channels = []
    
    # Search across all queries
    for query in SEARCH_QUERIES:
        logger.info(f"Searching: '{query}'")
        results = search_channels_by_query(query, max_results=10)
        
        for item in results:
            channel_id = item["id"]["channelId"]
            all_channel_ids.add(channel_id)
    
    logger.info(f"Found {len(all_channel_ids)} unique channels to analyze")
    
    # Analyze each channel
    for i, channel_id in enumerate(all_channel_ids, 1):
        logger.info(f"\n[{i}/{len(all_channel_ids)}] Analyzing channel...")
        
        # Get channel details
        channel_info = get_channel_details(channel_id)
        if not channel_info:
            continue
        
        # Skip channels with very low subscribers
        if channel_info["subscriber_count"] < 10_000:
            logger.info(f"⏭️  Skipping '{channel_info['title']}' - too few subscribers")
            continue
        
        # Get recent videos
        recent_videos = get_recent_videos(channel_id, max_results=5)
        
        # Analyze with Gemini
        analysis = analyze_channel_with_gemini(channel_info, recent_videos)
        
        if not analysis:
            continue
        
        score = analysis.get("score", 0)
        verdict = analysis.get("verdict", "SKIP")
        recommended = analysis.get("recommended", False)
        
        logger.info(f"📊 {channel_info['title']}")
        logger.info(f"   Score: {score}/100 | Verdict: {verdict}")
        logger.info(f"   Reasoning: {analysis.get('reasoning', 'N/A')}")
        
        # Add to recommendations if meets criteria
        if recommended and score >= min_score:
            recommended_channels.append({
                "title": channel_info["title"],
                "id": channel_info["id"],
                "subs": channel_info["subscriber_count"],
                "url": channel_info["url"],
                "ai_score": score,
                "verdict": verdict,
                "category": analysis.get("content_category", "unknown"),
                "viral_potential": analysis.get("viral_potential", "")
            })
            logger.info(f"   ✅ ADDED to recommendations!")
        
        # Stop if we have enough channels
        if len(recommended_channels) >= max_channels:
            logger.info(f"\n✅ Reached target of {max_channels} channels!")
            break
    
    # Sort by AI score
    recommended_channels.sort(key=lambda x: x["ai_score"], reverse=True)
    
    return recommended_channels

# ==================== MAIN ====================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🤖 AI-Powered Viral Channel Finder")
    logger.info("=" * 60)
    
    # Find channels
    channels = find_viral_channels(min_score=70, max_channels=15)
    
    if channels:
        logger.info(f"\n{'=' * 60}")
        logger.info(f"✅ Found {len(channels)} viral channels!")
        logger.info(f"{'=' * 60}\n")
        
        # Display results
        for i, ch in enumerate(channels, 1):
            logger.info(f"{i}. {ch['title']}")
            logger.info(f"   Subscribers: {ch['subs']:,}")
            logger.info(f"   AI Score: {ch['ai_score']}/100")
            logger.info(f"   Category: {ch['category']}")
            logger.info(f"   Verdict: {ch['verdict']}")
            logger.info(f"   Viral Potential: {ch['viral_potential'][:100]}...")
            logger.info("")
        
        # Insert into database
        logger.info("💾 Inserting channels into database...")
        db_insert_channel(channels)
        logger.info("✅ Database updated successfully!")
        
    else:
        logger.warning("❌ No suitable channels found.")
