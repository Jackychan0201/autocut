# AutoShorts

**AutoShorts** is a fully automated pipeline for creating viral short-form content from YouTube videos. It discovers channels, downloads videos, transcribes audio, identifies engaging moments using AI, and produces polished vertical clips ready for TikTok, Instagram Reels, or YouTube Shorts.

---

## 🎯 Overview

The pipeline consists of **7 main components** that work together:

1. **Database (PostgreSQL)** – Stores channels, videos, and metadata
2. **Scraper** – Discovers and tracks YouTube channels and videos
3. **Downloader** – Downloads videos using yt-dlp
4. **Transcriber** – Generates timestamped transcripts using Whisper AI
5. **Highlighter** – Identifies viral moments using Google Gemini AI
6. **Clipper** – Extracts highlight clips and formats them vertically
7. **Editor** – Adds captions, background videos, and hooks to create final shorts
8. **Uploader** – Automatically uploads edited clips to YouTube as Shorts

---

## 🗄️ Database Schema

The PostgreSQL database contains three tables:

### **Channels**
- `id` (SERIAL PRIMARY KEY)
- `name` (TEXT, UNIQUE) – Channel name
- `link` (TEXT, UNIQUE) – Channel URL

### **Videos**
- `id` (SERIAL PRIMARY KEY)
- `link` (TEXT, UNIQUE) – Video URL
- `is_downloaded` (BOOLEAN) – Download status
- `is_used` (BOOLEAN) – Processing status
- `channel_id` (INT, FOREIGN KEY) – Links to Channels table

### **Shorts**
- `id` (SERIAL PRIMARY KEY)
- `num_of_views` (INTEGER)
- `num_of_likes` (INTEGER)
- `num_of_comments` (INTEGER)

---

## 🔧 Components

### 1. **Scraper** (`scraper/`)

**Purpose**: Automatically discovers English-speaking podcast channels and tracks their latest videos.

**Key Files**:
- `ChannelFinder.py` – Searches for English podcast channels using YouTube Data API
  - Filters by language detection (using `langdetect`)
  - Filters by country (US, GB, CA, AU, NZ, IE)
  - Filters by minimum subscriber count
  - Inserts discovered channels into the database

- `LinkScraper.py` – Monitors channels and adds new videos
  - Fetches all channels from the database
  - Uses YouTube Data API to get latest videos
  - Filters videos by duration (≤15 minutes)
  - Resolves `@handles` to channel IDs
  - Inserts new videos with `is_downloaded=false`

**Features**:
- Supports channel URLs, user URLs, `@handles`, and direct video links
- Automatically filters videos by maximum duration (15 minutes)
- Prevents duplicate video entries

---

### 2. **Downloader** (`downloader/`)

**Purpose**: Downloads the highest quality video from YouTube.

**Key File**: `Downloader.py`

**Functionality**:
- Fetches the first undownloaded video from the database
- Downloads best video + audio using `yt-dlp`
- Uses Android player client for better compatibility
- Merges streams into a single MP4 file
- Marks video as downloaded in the database
- Saves to `/downloads` directory

**Download Options**:
- Format: Best video + best audio merged
- Output: MP4 container
- Quality: Highest available
- Custom User-Agent and headers for reliability

---

### 3. **Transcriber** (`transcriber/`)

**Purpose**: Generates accurate, timestamped transcriptions using OpenAI Whisper.

**Key File**: `Transcriber.py`

**Functionality**:
- Extracts audio from video using FFmpeg
  - Converts to 16kHz mono WAV
  - Applies volume normalization (1.5x)
- Transcribes using Whisper `small` model (upgradeable to `medium`/`large`)
- Generates **two transcript formats**:
  
  **Full Transcript** (`/transcripts/`):
  - Complete Whisper output with all metadata
  - Includes confidence scores, language detection
  
  **Simplified Transcript** (`/transcripts_simple/`):
  - Splits segments into 2-word chunks
  - Precise timestamps for word-level captions
  - Optimized for subtitle generation

**Output Format**:
```json
[
  {
    "start": 0.0,
    "end": 1.2,
    "text": "Hello world",
    "confidence": -0.234
  }
]
```

---

### 4. **Highlighter** (`highlighter/`)

**Purpose**: Uses AI to identify the most engaging, viral-worthy moments in videos.

**Key File**: `HighlightFinder.py`

**Functionality**:
- Loads simplified transcript
- Sends transcript to **Google Gemini 2.5 Flash** with specialized prompt
- AI identifies top 8 viral moments based on:
  - Emotional impact
  - Surprise factor
  - Humor
  - Insight/wisdom
  - Social media shareability

**Output Format** (`/highlights/`):
```json
[
  {
    "start": 45.2,
    "end": 68.5,
    "title": "Mind-Blowing Revelation",
    "summary": "Guest reveals shocking industry secret that changes everything"
  }
]
```

**Constraints**:
- Each highlight: 15-40 seconds
- No overlapping segments
- Variety across different parts of video
- Complete thoughts (no mid-sentence cuts)

---

### 5. **Clipper** (`clipper/`)

**Purpose**: Extracts highlight segments and formats them for vertical video (9:16).

**Key File**: `ClipGenerator.py`

**Functionality**:
- Loads highlights JSON
- Finds corresponding video in `/downloads`
- For each highlight:
  - Extracts segment using FFmpeg
  - Converts to vertical format (1080x1920)
  - Applies intelligent cropping to preserve important content
  - Saves to `/clips` with sanitized filename

**Video Processing**:
- Resolution: 1080x1920 (9:16 aspect ratio)
- Codec: H.264 (libx264)
- Quality: CRF 18 (high quality)
- Audio: AAC 128kbps
- Cropping: Centers on top 640px of scaled video

---

### 6. **Editor** (`editor/`)

**Purpose**: Creates polished, final shorts with captions, background videos, and hooks.

**Key File**: `VideoEditor.py`

**Functionality**:

**Caption Generation**:
- Loads simplified transcript for each clip
- Generates word-by-word captions using ASS subtitle format
- Applies custom styling:
  - Font: Futura Heavy (52pt)
  - Color: Customizable highlight color
  - Position: Bottom-centered
  - Timing: Synchronized with audio

**Background Video**:
- Overlays gameplay/B-roll footage from `/bg_videos`
- Scales and crops to fit vertical format
- Positioned behind main content
- Uses round-robin queue to avoid repetition

**Hook Videos**:
- Prepends attention-grabbing hooks from `/hooks`
- Automatically concatenates hook + main clip
- Maintains consistent formatting

**State Management**:
- Tracks used background videos and hooks in `video_usage_state.json`
- Implements queue system to cycle through assets
- Prevents repetition until all assets are used

**Output**: Final edited clips saved to `/edited_clips`

---

### 7. **Uploader** (`uploader/`)

**Purpose**: Automatically uploads edited `.mp4` videos to YouTube as Shorts.

**Key File**: `uploader.py`

**Functionality**:
- **Automatic Metadata**: Fetches viral titles and hashtags generated by the Highlighter.
- **One-Shot Upload**: Processes one video at a time to stay within API quotas and prevent accidental multi-uploads.
- **Folder Monitoring**: Monitors `/edited_clips` for new videos.
- **State Management**: Moves uploaded videos to `/edited_clips/uploaded/` after successful completion.

---

## 🚀 Setup & Installation

### Prerequisites
- Docker & Docker Compose
- YouTube Data API key ([Get one here](https://console.cloud.google.com/apis/credentials))
- Google Gemini API key ([Get one here](https://aistudio.google.com/app/apikey))

### 1. Clone the Repository

```bash
git clone <repo_url>
cd autoshorts
```

### 2. Create `.env` File

Create a `.env` file in the project root:

```dotenv
# Database Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=supersecretpassword
POSTGRES_DB=autocut_db
POSTGRES_HOST=db
POSTGRES_PORT=5432

# API Keys
YT_API_KEY=YOUR_YOUTUBE_API_KEY
GEMINI_API_KEY=YOUR_GEMINI_API_KEY

# Optional
USER_AGENT=AutoShorts/1.0 (+https://example.com)
```

### 3. Start the Database

```bash
docker-compose up -d db
```

### 4. Verify Database Tables

```bash
docker exec -it $(docker ps -qf "name=db") psql -U postgres -d autocut_db
```

In psql:
```sql
\dt  -- List tables
SELECT * FROM channels;  -- View channels
```

---

## 📋 Usage

### Automated Workflow (Recommended)
You can run the entire pipeline with a single command. The script will automatically decide whether to upload existing clips, process new videos from the DB, or scrape new content if the DB is empty.

```bash
python3 runner.py
```

### Manual Steps
If you prefer to run individual components:

Discover English-speaking podcast channels:

```bash
docker compose build --no-cache scraper
docker-compose run --rm scraper python ChannelFinder.py
```

### Step 2: Scrape Videos

Find and add new videos from tracked channels:

```bash
docker-compose run --rm scraper python LinkScraper.py
```

### Step 3: Download Video

Download the first unprocessed video:

```bash
docker compose build --no-cache downloader
docker-compose run --rm downloader python Downloader.py
```

### Step 4: Transcribe

Generate timestamped transcripts:

```bash
docker compose build --no-cache transcriber
docker-compose run --rm transcriber python Transcriber.py
```

**Output**:
- `/transcripts/` – Full Whisper output
- `/transcripts_simple/` – Word-level segments

### Step 5: Find Highlights

Use AI to identify viral moments:

```bash
docker compose build --no-cache highlighter
docker-compose run --rm highlighter python HighlightFinder.py
```

**Output**: `/highlights/` – JSON with top 8 moments

### Step 6: Generate Clips

Extract and format highlight clips:

```bash
docker compose build --no-cache clipper
docker-compose run --rm clipper python ClipGenerator.py
```

**Output**: `/clips/` – Vertical video clips (1080x1920)

### Step 7: Edit & Finalize

Add captions, backgrounds, and hooks:

```bash
docker compose build --no-cache editor
docker-compose run --rm editor python VideoEditor.py
```

**Output**: `/edited_clips/` – Final, publish-ready shorts

### Step 8: Upload to YouTube

Upload the next available clip as a YouTube Short:

```bash
docker compose build --no-cache uploader
docker-compose run --rm uploader python uploader.py
```

**Note**: Ensure you have followed the OAuth setup in `uploader/README.md` first.

---

## 📁 Directory Structure

```
autoshorts/
├── db_init/              # Database initialization scripts
│   ├── init.sql          # Creates tables
│   └── migration.sql     # Adds foreign keys and indexes
├── db_scripts/           # Shared database utilities
│   ├── db_connect.py     # PostgreSQL connection
│   ├── db_helpers.py     # Query helpers
│   └── db_insert.py      # Insert operations
├── scraper/              # Channel & video discovery
│   ├── ChannelFinder.py  # Find English podcast channels
│   └── LinkScraper.py    # Track new videos
├── downloader/           # Video downloading
│   └── Downloader.py     # yt-dlp wrapper
├── transcriber/          # Audio transcription
│   └── Transcriber.py    # Whisper AI transcription
├── highlighter/          # AI highlight detection
│   └── HighlightFinder.py # Gemini AI analysis
├── clipper/              # Video clipping
│   └── ClipGenerator.py  # FFmpeg clip extraction
├── editor/               # Final video editing
│   ├── VideoEditor.py    # Caption & composition
│   ├── fonts/            # Custom fonts
│   ├── bg_videos/        # Background footage
│   └── hooks/            # Attention-grabbing intros
├── downloads/            # Downloaded videos
├── transcripts/          # Full transcripts
├── transcripts_simple/   # Simplified transcripts
├── highlights/           # AI-identified moments
├── clips/                # Extracted clips
├── edited_clips/         # Final output
└── docker-compose.yml    # Service orchestration
```

---

## 🛠️ Advanced Configuration

### Whisper Model Selection

Edit `transcriber/Transcriber.py`:

```python
MODEL_NAME = "small"  # Options: tiny, base, small, medium, large
```

- **tiny/base**: Fast, lower accuracy
- **small**: Balanced (default)
- **medium/large**: Slower, higher accuracy

### Video Duration Filter

Edit `scraper/LinkScraper.py`:

```python
MAX_DURATION_MIN = 15  # Maximum video length in minutes
```

### Highlight Count

Edit `highlighter/HighlightFinder.py` prompt:

```python
"Return a VALID JSON array of EXACTLY 8 objects"  # Change 8 to desired count
```

### Caption Styling

Edit `editor/VideoEditor.py`:

```python
FONT_SIZE = 52           # Font size
HIGHLIGHT_COLOR = "&H00FFFFFF"  # White (ASS format)
MAX_WORDS_PER_LINE = 6   # Words per caption
```

---

## 🔄 Automation

### Run Full Pipeline

Create a bash script `run_pipeline.sh`:

```bash
#!/bin/bash
docker-compose run --rm scraper python LinkScraper.py
docker-compose run --rm downloader python Downloader.py
docker-compose run --rm transcriber python Transcriber.py
docker-compose run --rm highlighter python HighlightFinder.py
docker-compose run --rm clipper python ClipGenerator.py
docker-compose run --rm editor python VideoEditor.py
```

### Cron Job (Daily at 2 AM)

```bash
0 2 * * * cd /path/to/autoshorts && ./run_pipeline.sh >> /var/log/autoshorts.log 2>&1
```

---

## 🐛 Troubleshooting

### Database Connection Issues

```bash
# Check if database is running
docker ps | grep db

# View database logs
docker logs <db_container_id>

# Restart database
docker-compose restart db
```

### Download Failures

- Verify `YT_API_KEY` in `.env`
- Check video availability (region restrictions, age-gating)
- Update yt-dlp: `pip install -U yt-dlp`

### Transcription Issues

- Ensure FFmpeg is installed in container
- Check audio extraction: verify WAV file is created
- Try different Whisper model size

### Highlight Generation Failures

- Verify `GEMINI_API_KEY` in `.env`
- Check API quota limits
- Review Gemini API logs for errors

---

## 📊 Database Management

### View All Videos

```sql
SELECT v.id, v.link, v.is_downloaded, v.is_used, c.name as channel
FROM videos v
JOIN channels c ON v.channel_id = c.id
ORDER BY v.id DESC;
```

### Reset Video Status

```sql
UPDATE videos SET is_downloaded = FALSE, is_used = FALSE WHERE id = <video_id>;
```

### Add Channel Manually

```sql
INSERT INTO channels (name, link) 
VALUES ('Channel Name', 'https://youtube.com/@handle')
ON CONFLICT (name) DO NOTHING;
```

---

## 🎨 Customization

### Add Custom Fonts

1. Place `.ttf` or `.otf` files in `editor/fonts/`
2. Update `FONT_PATH` in `VideoEditor.py`
3. Rebuild editor container

### Add Background Videos

1. Add MP4 files to `editor/bg_videos/`
2. Videos will be automatically cycled

### Add Hook Videos

1. Add MP4 files to `editor/hooks/`
2. Hooks will be prepended to clips in rotation

---

## 📝 Notes

- **API Costs**: YouTube Data API has daily quotas; Gemini API may incur costs
- **Processing Time**: Full pipeline takes 5-15 minutes per video (depending on length)
- **Storage**: Each video + outputs requires ~500MB-2GB
- **Quality**: Higher Whisper models and video quality increase processing time
- **Legal**: Ensure you have rights to use source content; respect copyright laws

---

## 🤝 Contributing

Contributions are welcome! Areas for improvement:

- Multi-language support
- Custom AI prompts for different content types
- Automated uploading to social platforms
- Web UI for pipeline management
- Real-time progress tracking

---

## 📄 License

This project is provided as-is for educational purposes. Ensure compliance with YouTube's Terms of Service and content licensing when using this tool.

---

## 🔗 Resources

- [YouTube Data API Documentation](https://developers.google.com/youtube/v3)
- [OpenAI Whisper](https://github.com/openai/whisper)
- [Google Gemini API](https://ai.google.dev/)
- [yt-dlp Documentation](https://github.com/yt-dlp/yt-dlp)
- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)