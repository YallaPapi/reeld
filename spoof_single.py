"""
Generate 5 spoofed variations of a single video (no speed change).
- Crops: 3–7% width, 2–5% height
- Tail-only trim OR extend by duplicating last frame (3–8%); start is never trimmed
- Audio bitrate: 128–264 kbps
- Video: H.264 Baseline, -bf 0, GOP 250, 3–17 Mbps, preset medium, tune film; level varies (3.0/3.1)
- Encoder tag randomized (metadata)
- Optional upscale: random 1.0–2.0x in 0.1 steps (lanczos)
"""

import os
import json
import random
import string
import subprocess
from datetime import datetime, timedelta

# Config
INPUT_FILE = r"test_embed\DPj6ZAliCHh_embedded.mp4"
OUTPUT_DIR = r"test_embed\our_variations"
COUNT = 5

# Ranges
CROP_W_MIN, CROP_W_MAX = 0.93, 0.97   # keep 93–97% width (3–7% crop)
CROP_H_MIN, CROP_H_MAX = 0.95, 0.98   # keep 95–98% height (2–5% crop)
TRIM_MIN, TRIM_MAX = 0.03, 0.08       # 3–8% trim/extend
VBIT_MIN, VBIT_MAX = 3000, 17000      # kbps video
ABIT_MIN, ABIT_MAX = 128, 264         # kbps audio
PRESET = "p5"                         # NVENC preset (quality-oriented)
LEVELS = ["3.0", "3.1"]
ENCODER_TAGS = ["Lavf58.76.100", "Lavf60.3.100", "Lavf62.6.100"]
SCALE_FACTORS = [round(1.0 + 0.1 * i, 1) for i in range(0, 11)]  # 1.0 to 2.0


def rand_suffix(n=6):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def random_metadata():
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


def get_fps(path):
    """Best-effort fps from r_frame_rate."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        return 30.0
    rate = result.stdout.strip()
    if "/" in rate:
        num, den = rate.split("/")
        try:
            return float(num) / float(den)
        except Exception:
            return 30.0
    try:
        return float(rate)
    except Exception:
        return 30.0


def build_freeze_filters(duration, fps):
    return []


def make_one(idx):
    meta = random_metadata()
    w_keep = random.uniform(CROP_W_MIN, CROP_W_MAX)
    h_keep = random.uniform(CROP_H_MIN, CROP_H_MAX)
    v_bitrate = random.randint(VBIT_MIN, VBIT_MAX)
    a_bitrate = random.randint(ABIT_MIN, ABIT_MAX)
    level = random.choice(LEVELS)
    encoder_tag = random.choice(ENCODER_TAGS)
    scale_factor = random.choice(SCALE_FACTORS)
    duration = get_duration(INPUT_FILE)
    fps = get_fps(INPUT_FILE)

    # Decide trim vs extend (tail-only)
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

    base = os.path.splitext(os.path.basename(INPUT_FILE))[0]
    out_name = f"{base}_ourvar_{idx}_{rand_suffix()}.mp4"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, out_name)

    crop_filter = (
        f"crop=iw*{w_keep:.4f}:ih*{h_keep:.4f}:"
        f"(iw-iw*{w_keep:.4f})/2:(ih-ih*{h_keep:.4f})/2"
    )
    scale_filter = (
        f"scale=trunc(iw*{scale_factor:.1f}/2)*2:"
        f"trunc(ih*{scale_factor:.1f}/2)*2:flags=lanczos"
    )
    freeze_filters = build_freeze_filters(duration, fps)

    vf_parts = [crop_filter, scale_filter]
    if freeze_filters:
        vf_parts.extend(freeze_filters)
    if tpad_filter:
        vf_parts.append(tpad_filter.lstrip(","))
    vf_chain = ",".join(vf_parts)

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start_offset:.3f}",
        "-i", INPUT_FILE,
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
        "-bufsize", f"{v_bitrate*2}k",
        "-c:a", "aac",
        "-b:a", f"{a_bitrate}k",
        "-movflags", "+faststart",
        "-metadata", f"encoder={encoder_tag}",
        "-metadata", f"creation_time={meta['creation_time']}",
        "-metadata", f"title={meta['title']}",
        "-metadata", f"comment={meta['comment']}",
        "-metadata", f"make={meta['make']}",
        "-metadata", f"model={meta['model']}",
        out_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed for {out_name}: {result.stderr}")

    return {
        "output": out_path,
        "crop_w_pct": 100 * (1 - w_keep),
        "crop_h_pct": 100 * (1 - h_keep),
        "action": action,
        "trim_pct": trim_pct,
        "start_offset": start_offset,
        "new_duration": new_duration,
        "scale_factor": scale_factor,
        "fps_guess": fps,
        "v_bitrate_k": v_bitrate,
        "a_bitrate_k": a_bitrate,
        "preset": PRESET,
        "level": level,
        "encoder": encoder_tag,
    }


def main():
    outputs = []
    for i in range(1, COUNT + 1):
        info = make_one(i)
        outputs.append(info)
        print(
            f"[{i}/{COUNT}] OK {os.path.basename(info['output'])} | "
            f"crop {info['crop_w_pct']:.1f}%/{info['crop_h_pct']:.1f}% | "
            f"{info['action']} {info['trim_pct']*100:.1f}% | "
            f"v {info['v_bitrate_k']}k | a {info['a_bitrate_k']}k | "
            f"enc {info['encoder']} | preset {info['preset']} | level {info['level']} | scale {info['scale_factor']}x"
        )

    with open(os.path.join(OUTPUT_DIR, "our_variations_params.json"), "w", encoding="utf-8") as f:
        json.dump(outputs, f, indent=2)
    print(f"\nSaved params to {OUTPUT_DIR}\\our_variations_params.json")


if __name__ == "__main__":
    main()
