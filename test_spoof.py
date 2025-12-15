"""Quick test: Spoof 4 videos with 2 copies each to test analytics pipeline."""

import os
import sys
import json
import random
import string
import subprocess
import hashlib
import base64
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8')

# Analytics tracking
from analytics import Analytics
analytics = Analytics(script_name="test_spoof")

# TEST CONFIG - 4 videos, 2 copies each
INPUT_BASE = r"C:\Users\asus\Desktop\projects\reeld\grq"
OUTPUT_BASE = r"C:\Users\asus\Desktop\projects\reeld\spoofed\test_run"
MAX_VIDEOS = 4
SPOOFS_PER_VIDEO = 2
MAX_WORKERS = 4

# Spoof parameters
CROP_W_MIN, CROP_W_MAX = 0.93, 0.97
CROP_H_MIN, CROP_H_MAX = 0.95, 0.98
TRIM_MIN, TRIM_MAX = 0.03, 0.08
VBIT_MIN, VBIT_MAX = 3000, 17000
ABIT_MIN, ABIT_MAX = 128, 264
PRESET = "p5"
SCALE_FACTORS = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5]


def rand_suffix(n=6):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def generate_shortcode(filename):
    hash_bytes = hashlib.sha256(filename.encode('utf-8')).digest()
    b64 = base64.urlsafe_b64encode(hash_bytes).decode('ascii')
    return b64[:12]


def get_duration(path):
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=duration", "-of", "default=noprint_wrappers=1:nokey=1", path]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    result.check_returncode()
    return float(result.stdout.strip())


def spoof_video(args):
    input_path, output_path, idx, total = args
    start_time = time.time()

    if os.path.exists(output_path):
        print(f"[{idx}/{total}] SKIP (exists) {os.path.basename(output_path)}")
        analytics.track("videos_skipped_exists", 1)
        return True

    try:
        duration = get_duration(input_path)
        w_keep = random.uniform(CROP_W_MIN, CROP_W_MAX)
        h_keep = random.uniform(CROP_H_MIN, CROP_H_MAX)
        v_bitrate = random.randint(VBIT_MIN, VBIT_MAX)
        a_bitrate = random.randint(ABIT_MIN, ABIT_MAX)
        scale_factor = random.choice(SCALE_FACTORS)

        crop_filter = f"crop=iw*{w_keep:.4f}:ih*{h_keep:.4f}:(iw-iw*{w_keep:.4f})/2:(ih-ih*{h_keep:.4f})/2"
        scale_filter = f"scale=trunc(iw*{scale_factor:.1f}/2)*2:trunc(ih*{scale_factor:.1f}/2)*2:flags=lanczos"
        vf_chain = f"{crop_filter},{scale_filter}"

        cmd = [
            "ffmpeg", "-y", "-i", input_path, "-t", f"{duration:.3f}",
            "-vf", vf_chain, "-c:v", "h264_nvenc", "-preset", PRESET,
            "-bf", "0", "-g", "250", "-pix_fmt", "yuv420p", "-tune", "hq",
            "-b:v", f"{v_bitrate}k", "-c:a", "aac", "-b:a", f"{a_bitrate}k",
            "-movflags", "+faststart", output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        elapsed_ms = (time.time() - start_time) * 1000

        if result.returncode == 0:
            print(f"[{idx}/{total}] OK {os.path.basename(output_path)} ({elapsed_ms/1000:.1f}s)")
            analytics.track("videos_spoofed", 1)
            analytics.track("processing_time_ms", elapsed_ms)
            return True
        else:
            print(f"[{idx}/{total}] FAIL {os.path.basename(output_path)}")
            analytics.track("videos_spoofed_failed", 1)
            analytics.error("ffmpeg", result.stderr[:200] if result.stderr else "Unknown")
            return False

    except Exception as e:
        print(f"[{idx}/{total}] ERROR {os.path.basename(output_path)}: {e}")
        analytics.track("videos_spoofed_failed", 1)
        analytics.error("exception", str(e)[:200])
        return False


def main():
    print(f"=== Analytics Test Run ===")
    print(f"Processing {MAX_VIDEOS} videos x {SPOOFS_PER_VIDEO} copies = {MAX_VIDEOS * SPOOFS_PER_VIDEO} total")
    print(f"Output: {OUTPUT_BASE}\n")

    # Find input videos (limit to MAX_VIDEOS)
    input_videos = []
    for f in os.listdir(INPUT_BASE):
        if f.endswith(".mp4"):
            input_videos.append(os.path.join(INPUT_BASE, f))
            if len(input_videos) >= MAX_VIDEOS:
                break

    print(f"Found {len(input_videos)} input videos")

    # Create output dir
    os.makedirs(OUTPUT_BASE, exist_ok=True)

    # Build task list
    tasks = []
    for input_path in input_videos:
        shortcode = generate_shortcode(os.path.basename(input_path))
        for variant in range(1, SPOOFS_PER_VIDEO + 1):
            output_path = os.path.join(OUTPUT_BASE, f"{shortcode}-{variant}.mp4")
            tasks.append((input_path, output_path, len(tasks) + 1, MAX_VIDEOS * SPOOFS_PER_VIDEO))

    # Process
    success = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(spoof_video, task) for task in tasks]
        for future in as_completed(futures):
            if future.result():
                success += 1

    print(f"\n=== Complete: {success}/{len(tasks)} succeeded ===")

    # Flush analytics
    analytics.track("videos_processed_total", success)
    analytics.flush()
    print(f"Analytics saved to: {analytics.db_path}")
    print(f"\nRefresh dashboard at http://localhost:8080 to see results!")


if __name__ == "__main__":
    main()
