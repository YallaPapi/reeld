# Reeld - Video Spoofing Pipeline

**Reeld** is a Python-based tool designed for processing and "spoofing" video content, primarily to generate unique variations of base video clips. This is commonly used in social media content repurposing (e.g., Instagram Reels) to create algorithmically distinct versions of videos while scaling posts across multiple accounts. The pipeline includes video transformation with NVENC GPU encoding, LSB audio steganography for tracking, batch processing, a graphical user interface, and a real-time analytics dashboard.

## Project Overview & Purpose

- **Core Goal**: Take source videos (scraped from Instagram via Apify) and automatically generate multiple modified versions ("spoofs") that appear unique to platform algorithms.
- **Key Techniques**:
  - Visual transformations (cropping, scaling, duration modification via trim/extend).
  - NVENC GPU-accelerated H.264 encoding with randomized parameters.
  - Metadata randomization (creation time, device info, encoder tags).
  - LSB audio steganography for embedding trackable shortcodes.
  - AI-powered caption rewriting using Claude API.
- **Additional Features**:
  - Tkinter GUI for end-to-end pipeline execution.
  - AI clip transformation with Claude, Whisper, and ElevenLabs integration.
  - VA (Virtual Assistant) chunk distribution for scaling operations.
  - Real-time analytics dashboard with FastAPI backend and React frontend.
- **Use Case**: Bulk repurposing podcast/creator clips across multiple accounts with unique variations per video.

## Project Structure

```
reeld/
├── .claude/                  # Claude Code settings
│   └── settings.local.json   # Local permission settings
├── .gitignore                # Git ignore rules
├── docs/                     # Documentation
│   ├── mvp_improvement_plan.md
│   └── prd.md                # Product Requirements Document
├── frontend/                 # React analytics dashboard
│   ├── dist/                 # Production build
│   ├── src/                  # Source (App.jsx, main.jsx, index.css)
│   ├── package.json          # npm dependencies
│   └── vite.config.js        # Vite bundler config
├── accounts.txt              # Instagram Reels URLs for Apify scraping
├── a.json                    # Apify scrape output (large, gitignored)
├── analytics.py              # Thread-safe metrics collector (SQLite backend)
├── create_va_chunks.py       # Splits output CSV/videos for VA distribution
├── dashboard.py              # FastAPI REST API for analytics dashboard
├── embed_audio_id.py         # Embeds shortcode in audio via LSB steganography
├── extract_audio_id.py       # Extracts embedded shortcode from audio
├── PROJECT_DOCUMENTATION.md  # Extended documentation (partially outdated)
├── PRD.md                    # Product Requirements Document (copy)
├── reeld_gui.py              # Main GUI app (Tkinter) - complete pipeline
├── requirements.txt          # Python dependencies for dashboard
├── spoof_chunk.py            # Processes videos from chunk mapping JSON
├── spoof_single.py           # Spoofs a single video file (5 variations)
├── spoof_videos.py           # Batch spoofing with parallel NVENC encoding
├── template.csv              # Output CSV format template for scheduling tools
├── test_spoof.py             # Quick test script for analytics pipeline
├── transform_clip.py         # AI transformation: Claude + Whisper + ElevenLabs
└── readme.txt                # This file
```

- **Language**: ~90% Python, ~10% JavaScript/CSS (React frontend)
- **Size**: 11 Python scripts + React dashboard

## Key Components

### Video Spoofing Core

- **spoof_videos.py**: Batch processor using ThreadPoolExecutor. Walks input directory, applies random transformations, generates multiple spoofs per video (configurable via `SPOOFS_PER_VIDEO`). Uses NVENC for GPU-accelerated encoding. Outputs mapping and params JSON files.
  - Crop: 3-7% width, 2-5% height (center)
  - Duration: Trim or extend tail by 3-8%
  - Scale: 1.0-2.0x with lanczos
  - Bitrate: Video 3-17 Mbps, Audio 128-264 kbps
  - Metadata: Randomized creation time, device model, encoder tag

- **spoof_single.py**: Single-video version that creates 5 variations. Same transformation parameters as batch version. Useful for testing.

- **spoof_chunk.py**: Processes videos based on chunk mapping JSON files (from `chunks_organized/`). Takes chunk number as CLI argument. Used for distributed processing. **Note**: Uses different (lower) parameters than main scripts: scale 0.9-1.3x, video bitrate 800-1500 kbps for smaller output files.

### AI Transformation Pipeline

- **transform_clip.py**: Advanced transformation using AI services:
  1. Extracts audio and transcribes with OpenAI Whisper API
  2. Generates hook text using Claude API (claude-sonnet-4-5)
  3. Creates voiceover using ElevenLabs TTS
  4. Inserts AI segment: freeze frame + voiceover + caption overlay
  5. Concatenates: original intro + AI insert + rest of clip

  Requires environment variables: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`

### Watermarking / Tracking

- **embed_audio_id.py**: Embeds Instagram shortcode into audio using LSB (Least Significant Bit) steganography. Process:
  1. Extract audio as 16-bit PCM WAV
  2. Convert shortcode to binary with length header
  3. Modify LSB of audio samples
  4. Remux with original video as AAC

- **extract_audio_id.py**: Reverse process - extracts embedded shortcode from spoofed videos. Useful for tracking which original video a spoof came from.

### User Interface

- **reeld_gui.py**: Complete Tkinter desktop application with 4-step pipeline:
  1. **Load JSON**: Parses Apify scrape output
  2. **Download**: Fetches videos using yt-dlp (10 parallel workers)
  3. **Spoof**: Creates variations with NVENC (8 parallel workers)
  4. **Generate CSV**: Writes output with optional Claude caption rewriting

  Features: Progress bars, log output, configurable spoofs per video, API key input.

### Analytics & Dashboard

- **analytics.py**: Thread-safe metrics collector with SQLite backend. Tracks videos_processed, captions_generated, claude_api_calls, processing_times, and errors. Supports batch flushes for parallel workers. Can be disabled via `ANALYTICS_ENABLED=false` environment variable.

- **dashboard.py**: FastAPI REST API for the analytics dashboard. Provides endpoints:
  - `/api/metrics/today` - Today's metrics
  - `/api/metrics/{days}` - Metrics for last N days
  - `/api/runs` - Recent pipeline runs
  - `/api/pipeline-status` - Current pipeline status

  Run with: `uvicorn dashboard:app --reload --port 8080`

- **frontend/**: React dashboard built with Vite. Features KPI cards, charts, and runs table for real-time monitoring.

- **test_spoof.py**: Quick test script that spoofs 4 videos with 2 copies each to test the analytics pipeline integration.

### Distribution Tools

- **create_va_chunks.py**: Splits spoofed videos and CSV into smaller chunks for distribution to Virtual Assistants. Reads from chunk CSV files, copies videos to VA-specific directories, preserves CSV format.

### Data Files

- **accounts.txt**: Instagram Reels page URLs for scraping targets (podcasters, creators).
- **template.csv**: Output CSV format with columns: Text, Pinterest Source Url, LinkedIn Group Title, CatalogId, ProductIds, Source, Image/Video link. Compatible with social media scheduling tools.
- **a.json**: Apify scrape output containing shortcodes, captions, video URLs, etc. (gitignored due to size).

## Dependencies

Required Python packages (install via pip):
```
anthropic          # Claude API client
openai             # Whisper transcription
elevenlabs         # Text-to-speech
python-dotenv      # Environment variable loading
numpy              # Audio array manipulation
fastapi>=0.104.0   # Dashboard REST API
uvicorn>=0.24.0    # ASGI server for dashboard
pydantic>=2.0.0    # Data validation
```

Required system tools:
```
ffmpeg             # Video/audio processing (with NVENC support)
ffprobe            # Media analysis
yt-dlp             # Video downloading
```

For frontend development (optional):
```
node.js            # JavaScript runtime
npm                # Package manager (for frontend)
```

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/YallaPapi/reeld.git
   cd reeld
   ```

2. Install Python dependencies:
   ```
   pip install -r requirements.txt
   pip install anthropic openai elevenlabs python-dotenv numpy
   ```

3. Ensure ffmpeg with NVENC support is installed and in PATH.

4. Create `.env` file with API keys (for AI features):
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   OPENAI_API_KEY=sk-...
   ELEVENLABS_API_KEY=...
   ```

## Usage

### GUI Mode (Recommended)
```
python reeld_gui.py
```
1. Select Apify JSON file (scrape output)
2. Select output folder
3. Set spoofs per video (1-10)
4. Enable Claude caption rewriting (optional)
5. Click "Start Processing"

### Batch Spoofing (CLI)
Note: Scripts use hardcoded paths - edit `INPUT_BASE` and `OUTPUT_BASE` before running.
```
python spoof_videos.py
```

### Single Video Spoofing
Edit `INPUT_FILE` and `OUTPUT_DIR` in script, then:
```
python spoof_single.py
```

### Chunk-Based Processing
```
python spoof_chunk.py 1    # Process chunk 1
python spoof_chunk.py 2    # Process chunk 2
```

### AI Clip Transformation
Edit paths in script, then:
```
python transform_clip.py
```

### Audio ID Embedding
Edit paths in scripts, then:
```
python embed_audio_id.py   # Embed shortcodes
python extract_audio_id.py # Extract shortcodes
```

### VA Chunk Distribution
Edit `num_vas` and `videos_per_va` in script:
```
python create_va_chunks.py
```

### Analytics Dashboard
Start the backend API:
```
python dashboard.py
# or: uvicorn dashboard:app --reload --port 8080
```
Open `http://localhost:8080` in browser to view the React dashboard.

To run analytics test:
```
python test_spoof.py
```

## How It Works (Pipeline)

1. **Scraping**: Use Apify Instagram scraper with URLs from `accounts.txt`
2. **Input**: JSON from Apify containing video URLs, captions, shortcodes
3. **Download**: yt-dlp fetches videos organized by creator username
4. **Processing**:
   - Apply random crop, scale, duration modifications
   - Encode with NVENC (h264_nvenc, preset p5, tune hq)
   - Randomize metadata (creation time, device, encoder tag)
   - Optionally embed shortcode via audio steganography
5. **Caption Rewriting**: Claude rewrites captions in 3rd person with credits
6. **Output**:
   - Spoofed videos in output directory
   - CSV file for scheduling tool import
   - Mapping JSON for tracking
7. **Analytics**: Metrics tracked in SQLite, viewable via dashboard
8. **Distribution**: Split into VA chunks if scaling with assistants

## Configuration

Key constants in scripts (edit before running):

**spoof_videos.py**:
- `INPUT_BASE`: Source video directory
- `OUTPUT_BASE`: Spoofed video destination
- `MAX_WORKERS`: Parallel encoding threads (default: 8)
- `SPOOFS_PER_VIDEO`: Variations per input (default: 4)

**Transformation ranges**:
- Crop: 3-7% width, 2-5% height
- Trim/extend: 3-8% of duration
- Video bitrate: 3-17 Mbps
- Audio bitrate: 128-264 kbps
- Scale: 1.0-2.0x

**Analytics**:
- `ANALYTICS_ENABLED`: Set to "false" to disable tracking (default: true)
- `ANALYTICS_DB_PATH`: Path to SQLite database (default: analytics.db)

## Requirements

- Windows (paths are Windows-style, NVENC requires NVIDIA GPU)
- Python 3.8+
- NVIDIA GPU with NVENC support
- ffmpeg compiled with NVENC
- Internet connection for API calls (Claude, Whisper, ElevenLabs)

## Notes

- NVENC has session limits (~8 concurrent sessions) - adjust `MAX_WORKERS` if encoding fails
- Large JSON files (a.json) are gitignored due to size
- Downloaded videos are gitignored - redownload with GUI as needed
- All paths in scripts are hardcoded - edit before running
- API keys should be in `.env` file (gitignored for security)
