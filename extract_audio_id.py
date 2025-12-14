import os
import json
import subprocess
import wave
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

def binary_to_text(binary_str):
    """Convert binary string to text"""
    text = ''
    for i in range(0, len(binary_str), 8):
        byte = binary_str[i:i+8]
        if len(byte) == 8:
            text += chr(int(byte, 2))
    return text

def extract_data_from_audio(audio_path):
    """Extract embedded data from audio using LSB steganography"""
    try:
        # Read audio file
        with wave.open(audio_path, 'rb') as audio:
            frames = audio.readframes(audio.getnframes())

        # Convert to numpy array
        audio_data = np.frombuffer(frames, dtype=np.int16)

        # Extract LSBs
        binary_data = ''
        for i in range(len(audio_data)):
            binary_data += str(audio_data[i] & 1)

        # Read length header (first 32 bits)
        if len(binary_data) < 32:
            return None

        data_length = int(binary_data[:32], 2)

        # Extract actual data
        if len(binary_data) < 32 + data_length:
            return None

        data_binary = binary_data[32:32+data_length]

        # Convert to text
        extracted_text = binary_to_text(data_binary)

        return extracted_text

    except Exception as e:
        print(f"Error extracting data: {e}")
        return None

def process_spoofed_video(args):
    """Extract shortcode from spoofed video"""
    video_path, idx, total = args

    print(f"[{idx}/{total}] Extracting from {os.path.basename(video_path)}")

    temp_audio = f"temp_extract_{idx}.wav"

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
            return (video_path, None)

        # Extract embedded shortcode
        shortcode = extract_data_from_audio(temp_audio)

        if shortcode:
            print(f"[{idx}/{total}] ✓ Found: {shortcode}")
            return (video_path, shortcode)
        else:
            print(f"[{idx}/{total}] ✗ No data found")
            return (video_path, None)

    except Exception as e:
        print(f"[{idx}/{total}] ✗ Error: {e}")
        return (video_path, None)
    finally:
        # Cleanup temp file
        if os.path.exists(temp_audio):
            os.remove(temp_audio)

def main():
    SPOOFED_DIR = r"C:\Users\asus\Desktop\projects\reeld\spoofed"
    OUTPUT_FILE = "spoofed_mapping.json"
    MAX_WORKERS = 10

    print("Scanning for spoofed videos...")

    # Find all video files
    video_files = []
    for root, dirs, files in os.walk(SPOOFED_DIR):
        for file in files:
            if file.endswith('.mp4'):
                video_files.append(os.path.join(root, file))

    total = len(video_files)
    print(f"Found {total} spoofed videos")
    print(f"Using {MAX_WORKERS} workers\n")

    # Process videos in parallel
    tasks = [(path, idx+1, total) for idx, path in enumerate(video_files)]

    mapping = {}
    completed = 0
    success = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(process_spoofed_video, task) for task in tasks]

        for future in as_completed(futures):
            video_path, shortcode = future.result()
            if shortcode:
                mapping[video_path] = shortcode
                success += 1
            completed += 1

            if completed % 50 == 0:
                print(f"\n=== Progress: {completed}/{total} ({100*completed//total}%) ===\n")

    # Save mapping
    print(f"\nSaving mapping to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, indent=2)

    print(f"\nDone!")
    print(f"Successfully extracted: {success}/{total}")
    print(f"Failed: {total - success}")
    print(f"\nMapping saved to: {OUTPUT_FILE}")
    print(f"You can now use this to generate the final CSV with captions")

if __name__ == "__main__":
    main()
