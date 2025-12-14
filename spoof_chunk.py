"""
Spoof videos for a specific chunk using NVENC encoding.
Reads chunk mapping JSON and processes only those videos.

Usage: python spoof_chunk.py [chunk_number]
Example: python spoof_chunk.py 1
"""
import os
import sys
import json
import random
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

# Configuration
CHUNKS_DIR = "chunks_organized"
MAX_WORKERS = 8  # NVENC session limit (adjust if needed)

# Spoof ranges (mirrors spoof_single)
CROP_W_MIN, CROP_W_MAX = 0.93, 0.97   # keep 93-97% width (3-7% crop)
CROP_H_MIN, CROP_H_MAX = 0.95, 0.98   # keep 95-98% height (2-5% crop)
TRIM_MIN, TRIM_MAX = 0.03, 0.08       # 3-8% trim/extend (tail-only)
VBIT_MIN, VBIT_MAX = 800, 1500        # kbps video
ABIT_MIN, ABIT_MAX = 128, 264         # kbps audio
PRESET = "p5"
LEVELS = ["3.0", "3.1"]
ENCODER_TAGS = ["Lavf58.76.100", "Lavf60.3.100", "Lavf62.6.100"]
SCALE_FACTORS = [round(0.9 + 0.1 * i, 1) for i in range(0, 5)]  # 0.9 to 1.3


def generate_random_metadata():
    """Randomize basic metadata to avoid detection."""
    days_ago = random.randint(1, 730)
    random_date = datetime.now() - timedelta(days=days_ago)
    cameras = ["iPhone 14 Pro", "iPhone 13", "Samsung Galaxy S23", "Pixel 7", "iPhone 15"]
    return {
        "creation_time": random_date.strftime("%Y-%m-%d %H:%M:%S"),
        "title": f"Video_{random.randint(1000, 9999)}",
        "comment": f"Processed_{random.randint(10000, 99999)}",
        "make": random.choice(["Apple", "Samsung", "Google"]),
        "model": random.choice(cameras),
    }


def get_duration(path):
    """Get video duration using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    result.check_returncode()
    return float(result.stdout.strip())


def spoof_video(args):
    """Spoof a single video with NVENC encoding."""
    input_path, output_path, idx, total = args

    # Check if already exists
    if os.path.exists(output_path):
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        if size_mb > 0:  # Only skip if file has content
            print(f"[{idx}/{total}] SKIP {os.path.basename(output_path)} (already exists, {size_mb:.1f}MB)")
            return (input_path, output_path, True)

    # Create output directory
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        metadata = generate_random_metadata()
        duration = get_duration(input_path)

        # Randomize encoding parameters
        w_keep = random.uniform(CROP_W_MIN, CROP_W_MAX)
        h_keep = random.uniform(CROP_H_MIN, CROP_H_MAX)
        trim_pct = random.uniform(TRIM_MIN, TRIM_MAX)
        action = random.choice(["trim", "extend"])
        start_offset = 0.0
        new_duration = duration
        tpad_filter = ""

        if action == "trim":
            cut_total = duration * trim_pct
            new_duration = max(duration - cut_total, 0.1)
        else:
            extend = duration * trim_pct
            new_duration = duration
            tpad_filter = f",tpad=stop_mode=clone:stop_duration={extend:.3f}"

        v_bitrate = random.randint(VBIT_MIN, VBIT_MAX)
        a_bitrate = random.randint(ABIT_MIN, ABIT_MAX)
        level = random.choice(LEVELS)
        encoder_tag = random.choice(ENCODER_TAGS)
        scale_factor = random.choice(SCALE_FACTORS)

        # Build filter chain
        crop_filter = (
            f"crop=iw*{w_keep:.4f}:ih*{h_keep:.4f}:"
            f"(iw-iw*{w_keep:.4f})/2:(ih-ih*{h_keep:.4f})/2"
        )
        scale_filter = (
            f"scale=trunc(iw*{scale_factor:.1f}/2)*2:"
            f"trunc(ih*{scale_factor:.1f}/2)*2:flags=bicubic"
        )

        vf_parts = [crop_filter, scale_filter]
        if tpad_filter:
            vf_parts.append(tpad_filter.lstrip(","))
        vf_chain = ",".join(vf_parts)

        # Build ffmpeg command
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{start_offset:.3f}",
            "-i", input_path,
            "-t", f"{new_duration:.3f}",
            "-vf", vf_chain,
            "-c:v", "h264_nvenc",
            "-preset", PRESET,
            "-bf", "0",
            "-g", "250",
            "-pix_fmt", "yuv420p",
            "-tune", "hq",
            "-b:v", f"{v_bitrate}k",
            "-maxrate", f"{v_bitrate}k",
            "-bufsize", f"{v_bitrate * 2}k",
            "-c:a", "aac",
            "-b:a", f"{a_bitrate}k",
            "-movflags", "+faststart",
            "-metadata", f"encoder={encoder_tag}",
            "-metadata", f"creation_time={metadata['creation_time']}",
            "-metadata", f"title={metadata['title']}",
            "-metadata", f"comment={metadata['comment']}",
            "-metadata", f"make={metadata['make']}",
            "-metadata", f"model={metadata['model']}",
            output_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode == 0:
            file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(
                f"[{idx}/{total}] OK {os.path.basename(output_path)} ({file_size_mb:.1f}MB) | "
                f"crop {100 * (1 - w_keep):.1f}%/{100 * (1 - h_keep):.1f}% | "
                f"{action} {trim_pct * 100:.1f}% | v {v_bitrate}k | scale {scale_factor}x"
            )
            return (input_path, output_path, True)

        print(f"[{idx}/{total}] FAIL {os.path.basename(output_path)}")
        if result.stderr:
            error_lines = result.stderr.strip().split('\n')
            for line in error_lines[-3:]:
                print(f"  ERROR: {line}")
        return (input_path, output_path, False)

    except Exception as e:
        print(f"[{idx}/{total}] FAIL {os.path.basename(output_path)} - {str(e)}")
        return (input_path, output_path, False)


def main():
    # Get chunk number from command line
    if len(sys.argv) > 1:
        chunk_num = int(sys.argv[1])
    else:
        chunk_num = 1

    print(f"Spoofing videos for chunk {chunk_num}...")
    print(f"Using {MAX_WORKERS} parallel workers with NVENC\n")

    # Load chunk mapping
    mapping_file = Path(CHUNKS_DIR) / f"chunk_{chunk_num:02d}_mapping.json"

    if not mapping_file.exists():
        print(f"ERROR: {mapping_file} not found!")
        return

    with open(mapping_file, "r", encoding="utf-8") as f:
        chunk_mapping = json.load(f)

    print(f"Loaded {len(chunk_mapping)} video mappings from {mapping_file}")

    # Create tasks from mapping
    tasks = []
    for idx, item in enumerate(chunk_mapping, 1):
        input_path = item["input"]
        output_path = item["output"]
        tasks.append((input_path, output_path, idx, len(chunk_mapping)))

    # Process videos
    successful = 0
    failed = 0
    skipped = 0

    print(f"\nProcessing {len(tasks)} videos...\n")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(spoof_video, task) for task in tasks]

        for future in as_completed(futures):
            inp, outp, success = future.result()
            if success:
                if os.path.exists(outp):
                    size = os.path.getsize(outp)
                    if size > 0:
                        successful += 1
                    else:
                        skipped += 1
            else:
                failed += 1

            # Progress update every 50 videos
            completed = successful + failed + skipped
            if completed % 50 == 0:
                print(f"\n=== Progress: {completed}/{len(tasks)} ({successful} OK, {failed} FAIL, {skipped} SKIP) ===\n")

    print(f"\n{'='*60}")
    print(f"Done! Chunk {chunk_num} results:")
    print(f"  Successful: {successful}/{len(tasks)}")
    print(f"  Failed: {failed}")
    print(f"  Skipped: {skipped}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
