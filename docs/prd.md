# Reeld Project Documentation

## Overview
This is an automated Instagram video content reposting system that downloads videos, modifies them to avoid detection, extracts metadata, rewrites captions using AI, and exports everything to CSV for bulk upload.

---

## Project Architecture

### Data Flow Pipeline

```
1. Download Videos (parallel_download.py)
   ↓
2. Embed Shortcodes in Audio (embed_audio_id.py) [OPTIONAL - for tracking]
   ↓
3. Spoof Videos (spoof_videos.py)
   ↓
4. Extract Shortcodes from Spoofed Videos (extract_audio_id.py) [OPTIONAL - if step 2 was used]
   ↓
5. Generate Final CSV (generate_csv_from_mapping.py)
```

---

## File Descriptions

### Core Scripts

#### 1. **parallel_download.py**
**Purpose:** Downloads Instagram videos from scraped data

**Input:**
- `a.json` - Scraped Instagram data containing:
  - `shortCode` - Instagram video ID
  - `videoUrl` - Direct video download URL
  - `inputUrl` - Original Instagram profile URL
  - `caption` - Original caption text

**Output:**
- Videos organized in folders: `{username}/{shortcode}.mp4`
- Example: `2bears.1cave/DPj6ZAliCHh.mp4`

**Key Parameters:**
- `MAX_WORKERS = 50` - Parallel download threads

**How it works:**
1. Loads `a.json` with video metadata
2. Extracts username from `inputUrl` using regex
3. Downloads videos using `yt-dlp` into username folders
4. Skips already downloaded files
5. Shows progress with counters

---

#### 2. **embed_audio_id.py** (OPTIONAL)
**Purpose:** Embeds shortcode into video audio using LSB steganography for tracking after spoofing

**Input:**
- `a.json` - For shortcode/username mapping
- Downloaded videos in `{username}/{shortcode}.mp4`

**Output:**
- Embedded videos in `embedded/` directory
- Same folder structure preserved

**How it works:**
1. Extracts audio from video as WAV (PCM 16-bit)
2. Converts shortcode to binary string
3. Embeds binary data into Least Significant Bits (LSB) of audio samples
4. Adds 32-bit length header and terminator
5. Remuxes video with modified audio (AAC 192k)

**Key Parameters:**
- `MAX_WORKERS = 10` - Parallel processing threads

**Note:** This is optional - only needed if you want to recover shortcodes from spoofed videos later. Not required if you're directly mapping spoofed videos.

---

#### 3. **spoof_videos.py**
**Purpose:** Creates modified "spoofed" versions of videos to avoid Instagram's duplicate detection

**Input:**
- All `.mp4` files in the project directory (excluding `spoofed/` folder)
- Can process embedded videos or original downloads

**Output:**
- Spoofed videos in `spoofed/` directory (maintains folder structure)
- Filename format: `{original_name}_spoof_{random_suffix}.mp4`
- `spoofed_mapping.json` - Maps original paths to spoofed paths
- `spoof_params.json` - Logs all transformation parameters

**Spoofing Techniques:**
1. **Cropping:** Removes 3-7% width, 2-5% height (center crop)
2. **Duration Change:** Either:
   - Trim 3-8% from end (tail-only, start untouched)
   - OR extend 3-8% by duplicating last frame (tpad)
3. **Scaling:** Upscale 1.1x to 1.8x (0.1 increments) using Lanczos
4. **Video Encoding:** H.264 NVENC
   - Preset: p5 (quality-oriented)
   - No B-frames (-bf 0)
   - GOP: 250
   - Bitrate: 3-17 Mbps (randomized)
5. **Audio:** AAC 128-264 kbps (randomized)
6. **Metadata Randomization:**
   - Encoder tag: Lavf58.76.100 / Lavf60.3.100 / Lavf62.6.100
   - Creation time: Random date within last 2 years
   - Camera model: iPhone/Samsung/Pixel (randomized)
   - Level: 3.0 or 3.1

**Key Parameters:**
- `MAX_WORKERS = 24` - Parallel ffmpeg processes
- `PRESET = "p5"` - NVENC preset

**Output Example (`spoofed_mapping.json`):**
```json
{
  "C:\\Users\\asus\\Desktop\\projects\\reeld\\2bears.1cave\\DPj6ZAliCHh.mp4":
  "C:\\Users\\asus\\Desktop\\projects\\reeld\\spoofed\\2bears.1cave\\DPj6ZAliCHh_spoof_a7k2m9.mp4"
}
```

---

#### 4. **spoof_single.py**
**Purpose:** Test script - generates 5 spoofed variations of a single video

**Input:**
- Single video file specified in `INPUT_FILE`
- Default: `test_embed\DPj6ZAliCHh_embedded.mp4`

**Output:**
- 5 variations in `test_embed\our_variations\`
- `our_variations_params.json` - Parameters for each variation

**Use Case:** Testing spoofing parameters before running full batch

---

#### 5. **extract_audio_id.py** (OPTIONAL)
**Purpose:** Recovers embedded shortcodes from spoofed videos (only needed if you used embed_audio_id.py)

**Input:**
- Spoofed videos in `spoofed/` directory

**Output:**
- `spoofed_mapping.json` - Maps spoofed video paths to extracted shortcodes

**How it works:**
1. Extracts audio from spoofed video as WAV
2. Reads LSB from audio samples
3. Decodes 32-bit length header
4. Extracts binary data and converts to text (shortcode)

**Key Parameters:**
- `MAX_WORKERS = 10`

**Note:** Only needed if you embedded shortcodes in step 2. Otherwise, `spoof_videos.py` already creates the mapping file.

---

#### 6. **generate_csv_from_mapping.py** ⭐
**Purpose:** Final step - generates CSV for bulk Instagram upload with rewritten captions

**Input:**
- `spoofed_mapping.json` - Maps original videos to spoofed videos
- `a.json` - Original caption data
- `captions_index.json` - Prebuilt index of shortcode→caption (auto-generated from a.json)

**Output:**
- `final_output.csv` - Master CSV with all videos
- `final_output_part_001.csv`, `final_output_part_002.csv`, etc. - Chunked CSVs (~4500 rows each)

**CSV Format (matches template.csv):**
```csv
Text,Pinterest Source Url,LinkedIn Group Title,CatalogId(optional),ProductIdsSeparatedByComma(optional),Source,Image/Video link 1
```

**Columns:**
- `Text` - AI-rewritten caption (3rd person)
- `Pinterest Source Url` - Empty
- `LinkedIn Group Title` - Empty
- `CatalogId(optional)` - "catalogId="
- `ProductIdsSeparatedByComma(optional)` - "productIds="
- `Source` - "Manual"
- `Image/Video link 1` - Full path to spoofed video

**How it works:**
1. Loads `spoofed_mapping.json` (supports both dict and list formats)
2. Loads or builds caption index from `a.json`
3. For each spoofed video:
   - Extracts shortcode from original filename
   - Looks up caption and username from index
   - Calls Claude API to rewrite caption in 3rd person
   - Generates variant phrasing if same shortcode appears multiple times
4. Writes master CSV and chunks

**Key Parameters:**
- `CHUNK_SIZE_ROWS = 4500` - Rows per chunked CSV
- `USE_CLAUDE = "1"` - Enable/disable AI rewriting (set env var USE_CLAUDE=0 to disable)
- `API_KEY` - Anthropic Claude API key (hardcoded)

**Caption Rewriting:**
Uses Claude Sonnet 4 to transform 1st person captions to 3rd person for clip accounts:
- Original: "I can't believe this happened! #amazing"
- Rewritten: "@username shares an incredible moment that left them speechless #amazing"

---

#### 7. **process_and_export.py** (LEGACY)
**Purpose:** Earlier version of CSV generation (before spoofing workflow was added)

**Status:** Superseded by `generate_csv_from_mapping.py`

**Differences:**
- Uses original video paths instead of spoofed paths
- No support for mapping files
- Limited to first 5 entries (test mode)

---

### Supporting Data Files

#### **a.json**
Scraped Instagram data with complete video metadata:
```json
[{
  "id": "3739088920961884641",
  "shortCode": "DPj6ZAliCHh",
  "caption": "The best gift you could give Tim...",
  "videoUrl": "https://scontent-ord5-3.cdninstagram.com/...",
  "inputUrl": "https://instagram.com/2bears.1cave/",
  "ownerUsername": "2bears.1cave",
  "videoDuration": 20.248,
  ...
}]
```

#### **captions_index.json**
Fast lookup index (auto-generated from a.json):
```json
{
  "DPj6ZAliCHh": {
    "caption": "The best gift you could give Tim...",
    "user": "2bears.1cave"
  }
}
```

#### **spoofed_mapping.json**
Maps original videos to spoofed versions:
```json
{
  "C:\\path\\to\\original.mp4": "C:\\path\\to\\spoofed\\original_spoof_abc123.mp4"
}
```

Or list format:
```json
[{
  "input": "test_embed/DPj6ZAliCHh_embedded.mp4",
  "output": "test_embed/our_variations/DPj6ZAliCHh_embedded_ourvar_1_6rw2vu.mp4"
}]
```

#### **spoof_params.json**
Detailed transformation parameters for each spoofed video:
```json
[{
  "input": "C:\\path\\to\\original.mp4",
  "output": "C:\\path\\to\\spoofed.mp4",
  "crop_w_pct": 5.2,
  "crop_h_pct": 3.8,
  "action": "trim",
  "trim_pct": 0.0645,
  "scale_factor": 1.4,
  "v_bitrate_k": 8500,
  "a_bitrate_k": 192,
  "encoder": "Lavf60.3.100"
}]
```

---

## Complete Workflow

### Standard Workflow (Without Audio Embedding)

```bash
# Step 1: Download all videos from Instagram
python parallel_download.py
# Output: {username}/{shortcode}.mp4 files

# Step 2: Spoof all videos to avoid detection
python spoof_videos.py
# Output: spoofed/ directory + spoofed_mapping.json

# Step 3: Generate final CSV with rewritten captions
python generate_csv_from_mapping.py
# Output: final_output.csv + chunked CSVs
```

### Advanced Workflow (With Audio Embedding for Tracking)

```bash
# Step 1: Download videos
python parallel_download.py

# Step 2: Embed shortcodes in audio (for later recovery)
python embed_audio_id.py
# Output: embedded/ directory

# Step 3: Spoof embedded videos
# Edit spoof_videos.py INPUT_BASE to point to embedded/
python spoof_videos.py
# Output: spoofed/ directory

# Step 4: Extract shortcodes from spoofed videos
python extract_audio_id.py
# Output: spoofed_mapping.json (video_path → shortcode)

# Step 5: Generate CSV
python generate_csv_from_mapping.py
# Output: final_output.csv
```

---

## Current Issues & Next Steps

### Known Issues

1. **Mapping Format Mismatch**
   - `spoof_videos.py` creates: `{original_path: spoofed_path}`
   - `extract_audio_id.py` creates: `{spoofed_path: shortcode}`
   - `generate_csv_from_mapping.py` expects either format
   - **Solution:** Code already handles both dict and list formats (lines 95-105)

2. **Shortcode Extraction from Filename**
   - `generate_csv_from_mapping.py` tries to extract shortcode from `input_path` filename
   - Uses stem (filename without extension) directly
   - Falls back to splitting by `_` if not found
   - **Potential Issue:** If original filename doesn't contain shortcode, lookup will fail

3. **Caption Index Building**
   - First run builds index from `a.json` (slow)
   - Subsequent runs use cached `captions_index.json` (fast)
   - If `a.json` updated, delete `captions_index.json` to rebuild

### Recommendations

1. **Verify Mapping File Structure**
   ```bash
   python -c "import json; print(json.dumps(json.load(open('spoofed_mapping.json')), indent=2)[:500])"
   ```

2. **Test Caption Lookup**
   - Ensure filenames contain shortcodes
   - Or modify `generate_csv_from_mapping.py` to use alternative lookup method

3. **Disable AI Rewriting for Testing**
   ```bash
   set USE_CLAUDE=0
   python generate_csv_from_mapping.py
   ```

4. **Check API Rate Limits**
   - Claude API calls are sequential (not parallel)
   - Large batches may hit rate limits
   - Consider adding retry logic or delays

---

## Directory Structure

```
reeld/
├── a.json                          # Scraped Instagram data
├── captions_index.json             # Caption lookup index
├── spoofed_mapping.json            # Original→Spoofed mapping
├── spoof_params.json               # Spoofing parameters log
├── template.csv                    # CSV format template
├── final_output.csv                # Master output CSV
├── final_output_part_001.csv       # Chunked CSV
├── parallel_download.py            # Step 1: Download
├── embed_audio_id.py               # Step 2: Embed (optional)
├── spoof_videos.py                 # Step 3: Spoof
├── spoof_single.py                 # Test spoofer
├── extract_audio_id.py             # Step 4: Extract (optional)
├── generate_csv_from_mapping.py    # Step 5: Generate CSV ⭐
├── process_and_export.py           # Legacy CSV generator
├── {username}/                     # Downloaded videos
│   └── {shortcode}.mp4
├── embedded/                       # Videos with embedded IDs
│   └── {username}/
│       └── {shortcode}.mp4
└── spoofed/                        # Spoofed videos
    └── {username}/
        └── {shortcode}_spoof_*.mp4
```

---

## Technical Details

### Spoofing Algorithm (Anti-Detection)

**Goal:** Make each video appear unique to Instagram's duplicate detection system

**Techniques:**
1. **Visual Changes:**
   - Crop borders (removes frame-matching fingerprints)
   - Scale up (changes resolution/pixel values)

2. **Temporal Changes:**
   - Trim or extend duration (breaks timeline matching)
   - Only modifies end (keeps important start content)

3. **Encoding Changes:**
   - Randomized bitrates (changes file signature)
   - Varied encoder tags (changes container metadata)
   - Different GOP sizes and settings

4. **Metadata Changes:**
   - Random creation dates
   - Different camera models
   - Unique titles/comments

**Result:** Each spoofed video has different:
- File hash
- Video fingerprint
- Duration
- Resolution
- Metadata
- Bitrate signature

### LSB Steganography (Audio Embedding)

**Concept:** Hide data in least significant bit of audio samples (imperceptible to human ear)

**Format:**
```
[32-bit length][data bits][terminator: 11111111]
```

**Example:**
- Shortcode: "DPj6ZAliCHh"
- Binary: 01000100 01010000... (88 bits)
- Header: 00000000 00000000 00000000 01011000 (88 in binary)
- Total: 32 + 88 + 8 = 128 bits embedded

**Capacity:** ~1 bit per audio sample
- 44.1kHz stereo WAV: 88,200 samples/sec
- 20-second video: 1,764,000 bits capacity
- Shortcode: ~88 bits needed
- Plenty of headroom

---

## Troubleshooting

### "SKIP: no caption for shortcode X"
- Shortcode not found in `captions_index.json`
- Check if filename contains correct shortcode
- Verify `a.json` has entry for that shortcode
- Delete `captions_index.json` and regenerate

### "Error rewriting caption"
- API key invalid or rate limited
- Network connectivity issue
- Set `USE_CLAUDE=0` to skip AI rewriting

### FFmpeg errors
- Ensure FFmpeg installed with NVENC support
- Check NVIDIA GPU available (for h264_nvenc)
- Fallback: change codec to libx264 (slower, CPU-based)

### Mapping file format issues
- `generate_csv_from_mapping.py` supports both dict and list formats
- Check file with: `python -c "import json; print(type(json.load(open('spoofed_mapping.json'))))"`

---

## Performance Notes

- **parallel_download.py:** 50 workers = ~50 simultaneous downloads
- **spoof_videos.py:** 24 workers = 24 parallel FFmpeg encodes (GPU-limited)
- **embed_audio_id.py:** 10 workers = 10 parallel processes (CPU-limited)
- **generate_csv_from_mapping.py:** Sequential API calls (rate-limit friendly)

**Bottlenecks:**
- Download: Network bandwidth
- Spoofing: GPU encoding (NVENC)
- Embedding: CPU + FFmpeg
- CSV generation: Claude API rate limits

---

## Future Enhancements

1. **Batch API Calls:** Use Claude's batch API for caption rewriting
2. **Error Recovery:** Resume partial runs without reprocessing
3. **Quality Control:** Verify spoofed videos play correctly
4. **Duplicate Detection:** Check for already-posted content
5. **Analytics:** Track which spoofing parameters work best
6. **Auto-Upload:** Direct integration with Instagram API

---

## Security & Privacy

⚠️ **Important Notes:**
- API key is hardcoded in scripts (consider using environment variables)
- Videos are stored locally (ensure sufficient disk space)
- Respect Instagram's Terms of Service
- Copyright considerations for reposting content

---

## Dependencies

**Required:**
- Python 3.7+
- FFmpeg (with NVENC support for GPU encoding)
- yt-dlp (for Instagram downloads)
- Python packages:
  - anthropic (Claude API)
  - numpy (audio processing)
  - concurrent.futures (parallel processing)

**Installation:**
```bash
pip install anthropic numpy
# FFmpeg: download from ffmpeg.org
# yt-dlp: pip install yt-dlp
```

---

## Summary

This is a sophisticated content repurposing pipeline that:
1. ✅ Downloads Instagram videos with metadata
2. ✅ (Optional) Embeds tracking IDs in audio
3. ✅ Creates undetectable spoofed variations
4. ✅ (Optional) Recovers tracking IDs after spoofing
5. ✅ Rewrites captions using AI
6. ✅ Exports to bulk upload CSV format

**Current Status:** All core components working. Main script is `generate_csv_from_mapping.py` for the final CSV generation step.

**Primary Use Case:** Automated Instagram clips/reels reposting account with AI-generated captions.

---

## VA Chunks (Mini Chunks for Virtual Assistants)

### Overview
The `create_va_chunks.py` script creates smaller chunk packages for distribution to VAs, containing a subset of videos and corresponding CSV data.

### Script: create_va_chunks.py

**Purpose:** Create mini chunks with N videos each for VA distribution

**Configuration:**
- `num_vas = 5` - Number of VA chunks to create
- `videos_per_va = 3` - Videos per chunk

**Input:**
- `chunk_01b.csv`, `chunk_01c.csv` - Source CSV files with video/caption data

**Output:**
- `va_chunk_01/` through `va_chunk_05/` directories
- Each contains: videos + `va_chunk_XX.csv`

**How it works:**
1. Reads source CSVs with `csv.reader` (handles multiline captions)
2. Groups videos by creator (extracts from video path)
3. Round-robin selection across creators for variety
4. Copies videos to VA chunk directories
5. Writes CSV with manual formatting to match source format exactly

### Current Issue (Unresolved)

**Problem:** CSV files generated by `create_va_chunks.py` do not parse correctly in Google Sheets - all data appears in a single column instead of being split across columns.

**Investigation Summary:**
- Source CSVs (chunk_01b.csv) work correctly in Google Sheets
- Output CSVs appear byte-for-byte identical in format
- Both use: UTF-8 encoding, CRLF line endings, same quoting rules
- Tested multiple approaches:
  - `csv.DictWriter` - doesn't work
  - `csv.writer` - doesn't work
  - Manual line copying - doesn't work (breaks multiline fields)
  - Manual CSV formatting with explicit quoting rules - doesn't work
  - Preserving full file paths vs relative paths - no difference

**Theories:**
1. Something about how the original CSVs were generated (from JSON parsing) that isn't captured
2. Google Sheets may have inconsistent behavior with small files vs large files
3. Possible invisible character or encoding difference not detected in byte comparison

**Workaround:**
- Manually copy rows from working chunk CSV files
- Or import VA chunk CSV and manually set delimiter to comma in Google Sheets

**Files:**
- Working source: `chunk_01b.csv`, `chunk_01c.csv`
- Script: `create_va_chunks.py`
- Output: `va_chunk_01/` through `va_chunk_05/`

---
