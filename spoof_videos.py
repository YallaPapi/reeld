"""
Multi-file video spoofer matching spoof_single NVENC pipeline.
- Crop 3-7% width, 2-5% height (center)
- Tail-only trim OR extend (tpad clone) by 3-8% (start untouched)
- Scale 1.1-1.8x (0.1 steps, lanczos)
- Video: h264_nvenc preset p5, tune hq, GOP 250, no B-frames, 3-17 Mbps
- Audio: AAC 128-264 kbps
- Keeps shortcode in filename, logs mapping and params
"""

import os
import sys
import json
import random
import string
import subprocess
import hashlib
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

# Fix Windows console encoding for Unicode filenames
sys.stdout.reconfigure(encoding='utf-8')

# Base configuration
INPUT_BASE = r"C:\Users\asus\Desktop\projects\reeld\grq"
OUTPUT_BASE = r"C:\Users\asus\Desktop\projects\reeld\spoofed\grq"
MAPPING_FILE = "grq_spoofed_mapping.json"
PARAMS_FILE = "grq_spoof_params.json"
MAX_WORKERS = 8  # NVENC session limit (adjust if you get failures)
SPOOFS_PER_VIDEO = 4  # How many spoofed variations to create per video (configurable)

# Ranges (mirrors spoof_single)
CROP_W_MIN, CROP_W_MAX = 0.93, 0.97   # keep 93-97% width (3-7% crop)
CROP_H_MIN, CROP_H_MAX = 0.95, 0.98   # keep 95-98% height (2-5% crop)
TRIM_MIN, TRIM_MAX = 0.03, 0.08       # 3-8% trim/extend (tail-only)
VBIT_MIN, VBIT_MAX = 3000, 17000      # kbps video
ABIT_MIN, ABIT_MAX = 128, 264         # kbps audio
PRESET = "p5"                         # NVENC preset (quality-oriented)
LEVELS = ["3.0", "3.1"]
ENCODER_TAGS = ["Lavf58.76.100", "Lavf60.3.100", "Lavf62.6.100"]
SCALE_FACTORS = [round(1.0 + 0.1 * i, 1) for i in range(0, 11)]  # 1.0 to 2.0 (matches spoof_single)


def rand_suffix(n=6):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def generate_shortcode(filename):
    """Generate a 12-character shortcode from filename hash."""
    # Hash the filename
    hash_bytes = hashlib.sha256(filename.encode('utf-8')).digest()
    # Base64 encode and take first 12 chars, replacing +/ with _-
    b64 = base64.urlsafe_b64encode(hash_bytes).decode('ascii')
    return b64[:12]


def generate_random_metadata():
    """Randomize basic metadata to avoid reuse."""
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
    """Spoof a single video with spoof_single settings (NVENC pipeline)."""
    input_path, output_path, idx, total, params = args

    if os.path.exists(output_path):
        print(f"[{idx}/{total}] {os.path.basename(output_path)} already exists")
        return (input_path, output_path, True, params)

    try:
        metadata = generate_random_metadata()
        duration = get_duration(input_path)

        # Randomize within spoof_single bounds
        w_keep = random.uniform(CROP_W_MIN, CROP_W_MAX)
        h_keep = random.uniform(CROP_H_MIN, CROP_H_MAX)
        trim_pct = random.uniform(TRIM_MIN, TRIM_MAX)
        action = random.choice(["trim", "extend"])
        start_offset = 0.0  # never trim start
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

        crop_filter = (
            f"crop=iw*{w_keep:.4f}:ih*{h_keep:.4f}:"
            f"(iw-iw*{w_keep:.4f})/2:(ih-ih*{h_keep:.4f})/2"
        )
        scale_filter = (
            f"scale=trunc(iw*{scale_factor:.1f}/2)*2:"
            f"trunc(ih*{scale_factor:.1f}/2)*2:flags=lanczos"
        )

        vf_parts = [crop_filter, scale_filter]
        if tpad_filter:
            vf_parts.append(tpad_filter.lstrip(","))
        vf_chain = ",".join(vf_parts)

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
            print(
                f"[{idx}/{total}] OK {os.path.basename(output_path)} | "
                f"crop {100 * (1 - w_keep):.1f}%/{100 * (1 - h_keep):.1f}% | "
                f"{action} {trim_pct * 100:.1f}% | v {v_bitrate}k | a {a_bitrate}k | "
                f"scale {scale_factor}x | enc {encoder_tag}"
            )
            params.update(
                {
                    "crop_w_pct": 100 * (1 - w_keep),
                    "crop_h_pct": 100 * (1 - h_keep),
                    "action": action,
                    "trim_pct": trim_pct,
                    "start_offset": start_offset,
                    "new_duration": new_duration,
                    "scale_factor": scale_factor,
                    "v_bitrate_k": v_bitrate,
                    "a_bitrate_k": a_bitrate,
                    "preset": PRESET,
                    "level": level,
                    "encoder": encoder_tag,
                }
            )
            return (input_path, output_path, True, params)

        print(f"[{idx}/{total}] FAIL {os.path.basename(output_path)}")
        if result.stderr:
            error_lines = result.stderr.strip().split('\n')
            # Print last 3 lines of error (usually most relevant)
            for line in error_lines[-3:]:
                print(f"  ERROR: {line}")
        return (input_path, output_path, False, params)

    except Exception as e:
        print(f"[{idx}/{total}] FAIL {os.path.basename(output_path)} - {str(e)}")
        return (input_path, output_path, False, params)


def main():
    print("Scanning for videos...")

    # Find all input videos
    input_videos = []
    for root, _, files in os.walk(INPUT_BASE):
        if OUTPUT_BASE in root:
            continue
        for file in files:
            if file.endswith(".mp4"):
                input_path = os.path.join(root, file)
                input_videos.append(input_path)

    # Create multiple spoof tasks per video
    video_files = []
    os.makedirs(OUTPUT_BASE, exist_ok=True)

    for input_path in input_videos:
        base = os.path.basename(input_path)
        # Generate 12-char shortcode from original filename
        shortcode = generate_shortcode(base)

        # Create SPOOFS_PER_VIDEO variations
        for variant_num in range(1, SPOOFS_PER_VIDEO + 1):
            out_name = f"{shortcode}-{variant_num}.mp4"
            output_path = os.path.join(OUTPUT_BASE, out_name)
            video_files.append((input_path, output_path))

    total = len(video_files)
    print(f"Found {len(input_videos)} input videos")
    print(f"Creating {SPOOFS_PER_VIDEO} spoofs per video = {total} total spoofs")
    print(f"Using {MAX_WORKERS} parallel workers")
    print(f"Output directory: {OUTPUT_BASE}\n")

    tasks = []
    for idx, (inp, out) in enumerate(video_files):
        tasks.append((inp, out, idx + 1, total, {"input": inp, "output": out}))

    mapping = []
    params_log = []
    completed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(spoof_video, task) for task in tasks]

        for future in as_completed(futures):
            input_path, output_path, success, p = future.result()
            if success:
                mapping.append({"input": input_path, "output": output_path})
                params_log.append(p)
            completed += 1

            if total and completed % 50 == 0:
                print(f"\n=== Progress: {completed}/{total} ({100 * completed // total}%) ===\n")

    print(f"\nSaving mapping to {MAPPING_FILE}...")
    with open(MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2)

    print(f"Saving params to {PARAMS_FILE}...")
    with open(PARAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(params_log, f, indent=2)

    print(f"\nDone! Processed {len(mapping)}/{total} videos successfully")
    print(f"Spoofed videos saved to: {OUTPUT_BASE}")
    print(f"Mapping file: {MAPPING_FILE}")
    print(f"Params log: {PARAMS_FILE}")


if __name__ == "__main__":
    main()
