import os
import json
import subprocess
import re
import wave
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

def text_to_binary(text):
    """Convert text to binary string"""
    return ''.join(format(ord(c), '08b') for c in text)

def embed_data_in_audio(audio_path, output_path, data_string):
    """Embed data into audio using LSB steganography"""
    try:
        # Read audio file
        with wave.open(audio_path, 'rb') as audio:
            params = audio.getparams()
            frames = audio.readframes(params.nframes)

        # Convert to numpy array
        audio_data = np.frombuffer(frames, dtype=np.int16)

        # Convert data to binary
        binary_data = text_to_binary(data_string)
        # Add length header and terminator
        binary_data = format(len(binary_data), '032b') + binary_data + '11111111'

        # Check if audio is long enough
        if len(binary_data) > len(audio_data):
            print(f"Error: Audio too short for data")
            return False

        # Embed data in LSB
        audio_copy = audio_data.copy()
        for i, bit in enumerate(binary_data):
            # Modify LSB
            if bit == '1':
                audio_copy[i] = audio_copy[i] | 1
            else:
                audio_copy[i] = audio_copy[i] & ~1

        # Write modified audio
        with wave.open(output_path, 'wb') as output:
            output.setparams(params)
            output.writeframes(audio_copy.tobytes())

        return True

    except Exception as e:
        print(f"Error embedding data: {e}")
        return False

def process_video(args):
    """Process single video - extract audio, embed ID, remux"""
    video_path, shortcode, username, idx, total, output_base = args

    # Create output path
    rel_path = os.path.relpath(video_path, r"C:\Users\asus\Desktop\projects\reeld")
    output_video = os.path.join(output_base, rel_path)
    os.makedirs(os.path.dirname(output_video), exist_ok=True)

    if os.path.exists(output_video):
        print(f"[{idx}/{total}] {username}/{shortcode} already embedded")
        return True

    print(f"[{idx}/{total}] Embedding {username}/{shortcode}")

    temp_audio = f"temp_audio_{idx}.wav"
    temp_audio_embedded = f"temp_audio_embedded_{idx}.wav"

    try:
        # Extract audio as WAV
        extract_cmd = [
            'ffmpeg', '-i', video_path,
            '-vn',  # No video
            '-acodec', 'pcm_s16le',  # 16-bit PCM
            '-ar', '44100',  # Sample rate
            '-ac', '2',  # Stereo
            '-y',
            temp_audio
        ]

        result = subprocess.run(extract_cmd, capture_output=True, timeout=60)
        if result.returncode != 0:
            print(f"[{idx}/{total}] ✗ Failed to extract audio")
            return False

        # Embed shortcode in audio
        if not embed_data_in_audio(temp_audio, temp_audio_embedded, shortcode):
            return False

        # Remux video with modified audio
        remux_cmd = [
            'ffmpeg',
            '-i', video_path,  # Original video
            '-i', temp_audio_embedded,  # Modified audio
            '-c:v', 'copy',  # Copy video stream
            '-c:a', 'aac',  # Encode audio to AAC
            '-b:a', '192k',  # Audio bitrate
            '-map', '0:v:0',  # Video from first input
            '-map', '1:a:0',  # Audio from second input
            '-y',
            output_video
        ]

        result = subprocess.run(remux_cmd, capture_output=True, timeout=120)

        if result.returncode == 0:
            print(f"[{idx}/{total}] ✓ {username}/{shortcode}")
            return True
        else:
            print(f"[{idx}/{total}] ✗ Failed to remux")
            return False

    except Exception as e:
        print(f"[{idx}/{total}] ✗ Error: {e}")
        return False
    finally:
        # Cleanup temp files
        for f in [temp_audio, temp_audio_embedded]:
            if os.path.exists(f):
                os.remove(f)

def main():
    INPUT_BASE = r"C:\Users\asus\Desktop\projects\reeld"
    OUTPUT_BASE = r"C:\Users\asus\Desktop\projects\reeld\embedded"
    MAX_WORKERS = 10  # Lower for CPU-intensive work

    print("Loading a.json...")
    with open('a.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Prepare tasks
    tasks = []
    for idx, item in enumerate(data, 1):
        shortcode = item.get('shortCode', '')
        input_url = item.get('inputUrl', '')

        if not shortcode or not input_url:
            continue

        # Extract username
        match = re.search(r'instagram\.com/([^/]+)', input_url)
        if not match:
            continue

        username = match.group(1)
        video_path = os.path.join(INPUT_BASE, username, f"{shortcode}.mp4")

        if not os.path.exists(video_path):
            continue

        tasks.append((video_path, shortcode, username, idx, len(data), OUTPUT_BASE))

    total = len(tasks)
    print(f"Processing {total} videos with {MAX_WORKERS} workers")
    print(f"Output: {OUTPUT_BASE}\n")

    completed = 0
    success = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(process_video, task) for task in tasks]

        for future in as_completed(futures):
            result = future.result()
            if result:
                success += 1
            completed += 1

            if completed % 50 == 0:
                print(f"\n=== Progress: {completed}/{total} ({100*completed//total}%) ===\n")

    print(f"\nDone! {success}/{total} videos embedded successfully")
    print(f"Embedded videos in: {OUTPUT_BASE}")
    print(f"\nNext steps:")
    print(f"1. Send videos from {OUTPUT_BASE} to Telegram bot")
    print(f"2. Run extract_audio_id.py on spoofed videos to recover shortcodes")

if __name__ == "__main__":
    main()
