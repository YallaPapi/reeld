"""
Transform a single clip with AI-generated hook INSERTED after the opening.

Format:
1. First ~5 seconds of clip plays (the viral hook)
2. FREEZE FRAME + AI voiceover + big caption (the transformation)
3. Rest of clip plays

This keeps the viral hook intact while adding transformative content.
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

import anthropic
from openai import OpenAI
from elevenlabs import ElevenLabs

# API Keys from environment variables
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")

# Configuration
INTRO_DURATION = 5.0  # Seconds of original clip before AI insert

# Initialize clients
claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def extract_audio(video_path: str, output_path: str) -> bool:
    """Extract audio from video as WAV."""
    cmd = [
        'ffmpeg', '-y', '-i', video_path,
        '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def transcribe_audio(audio_path: str) -> str:
    """Transcribe audio using OpenAI Whisper API."""
    client = OpenAI(api_key=OPENAI_API_KEY)

    with open(audio_path, 'rb') as f:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="text"
        )
    return transcript


def generate_hook(transcript: str, creator: str) -> str:
    """Generate compelling hook using Claude."""
    response = claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": f"""Write a compelling 8-10 word hook for this podcast clip.

Creator: {creator}
Transcript: {transcript[:1500]}

Requirements:
- Start with the creator's name (use natural version, e.g. "Joe Rogan" not "joeroganexperience")
- Tease the most interesting part of the content
- Create curiosity - make people want to keep watching
- MUST be 8-10 words MAXIMUM (this is critical)
- Be punchy and direct

Output ONLY the hook text, nothing else. No quotes."""
        }]
    )
    return response.content[0].text.strip()


def generate_voiceover(text: str, output_path: str) -> bool:
    """Generate voiceover using ElevenLabs with energetic voice."""
    client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

    audio = client.text_to_speech.convert(
        text=text,
        voice_id="TxGEqnHWrfWFTfGW9XjX",  # "Josh" - energetic, young male
        model_id="eleven_turbo_v2_5",
        output_format="mp3_44100_128",
        voice_settings={
            "stability": 0.3,  # Lower = more expressive
            "similarity_boost": 0.8,
            "style": 0.8,  # Higher = more energetic
            "use_speaker_boost": True
        }
    )

    with open(output_path, 'wb') as f:
        for chunk in audio:
            f.write(chunk)

    return os.path.exists(output_path)


def get_audio_duration(audio_path: str) -> float:
    """Get duration of audio file in seconds."""
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        audio_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())


def get_video_duration(video_path: str) -> float:
    """Get duration of video file in seconds."""
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())


def get_video_properties(video_path: str) -> dict:
    """Get video resolution and fps."""
    cmd = [
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,r_frame_rate',
        '-of', 'csv=p=0',
        video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    parts = result.stdout.strip().split(',')
    width, height = int(parts[0]), int(parts[1])
    fps_parts = parts[2].split('/')
    fps = int(fps_parts[0]) / int(fps_parts[1]) if len(fps_parts) == 2 else float(fps_parts[0])
    return {'width': width, 'height': height, 'fps': fps}


def extract_frame_at_time(video_path: str, time_sec: float, output_path: str) -> bool:
    """Extract a single frame at specific time."""
    cmd = [
        'ffmpeg', '-y', '-ss', str(time_sec), '-i', video_path,
        '-vframes', '1', '-q:v', '2',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def split_video(video_path: str, split_time: float, part1_path: str, part2_path: str) -> bool:
    """Split video into two parts at specified time."""
    # Part 1: 0 to split_time
    cmd1 = [
        'ffmpeg', '-y', '-i', video_path,
        '-t', str(split_time),
        '-c:v', 'h264_nvenc', '-preset', 'p5',
        '-c:a', 'aac', '-b:a', '192k',
        part1_path
    ]
    result1 = subprocess.run(cmd1, capture_output=True, text=True)

    # Part 2: split_time to end
    cmd2 = [
        'ffmpeg', '-y', '-ss', str(split_time), '-i', video_path,
        '-c:v', 'h264_nvenc', '-preset', 'p5',
        '-c:a', 'aac', '-b:a', '192k',
        part2_path
    ]
    result2 = subprocess.run(cmd2, capture_output=True, text=True)

    return result1.returncode == 0 and result2.returncode == 0


def wrap_text_for_video(text: str, max_chars_per_line: int = 20) -> str:
    """Wrap text into multiple lines for video display."""
    words = text.split()
    lines = []
    current_line = []
    current_length = 0

    for word in words:
        if current_length + len(word) + 1 <= max_chars_per_line:
            current_line.append(word)
            current_length += len(word) + 1
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
            current_length = len(word)

    if current_line:
        lines.append(' '.join(current_line))

    return '\n'.join(lines)


def create_ai_insert(frame_path: str, audio_path: str, hook_text: str,
                     output_path: str, width: int, height: int, fps: float,
                     temp_dir: str) -> bool:
    """Create the AI insert: freeze frame + voiceover + big serif caption.

    Uses textfile parameter for multi-line text because FFmpeg drawtext
    does NOT interpret \\n as newlines - it needs actual newline characters
    in a file. See: https://stackoverflow.com/questions/8213865
    """
    duration = get_audio_duration(audio_path)

    # Wrap text to fit on screen (20 chars per line for readability)
    wrapped_text = wrap_text_for_video(hook_text, max_chars_per_line=20)
    print(f"  Wrapped text:")
    for line in wrapped_text.split('\n'):
        print(f"    {line}")

    # Write text to a temp file (FFmpeg textfile reads actual newlines)
    text_file_path = os.path.join(temp_dir, "caption.txt")
    with open(text_file_path, 'w', encoding='utf-8') as f:
        f.write(wrapped_text)

    # Convert Windows path for FFmpeg: C:\path -> C\:/path (escape colon, use forward slashes)
    ffmpeg_text_path = text_file_path.replace('\\', '/').replace(':', '\\:')

    # BIG font - 8% of height, minimum 48px
    font_size = max(48, int(height * 0.08))

    box_padding = 30

    # Serif font, centered, with semi-transparent background box
    # Using textfile= instead of text= for proper multi-line support
    drawtext_filter = (
        f"drawtext=textfile='{ffmpeg_text_path}':"
        f"fontfile='C\\:/Windows/Fonts/times.ttf':"
        f"fontsize={font_size}:"
        f"fontcolor=white:"
        f"borderw=4:"
        f"bordercolor=black:"
        f"x=(w-text_w)/2:"
        f"y=(h-text_h)/2:"
        f"box=1:"
        f"boxcolor=black@0.6:"
        f"boxborderw={box_padding}:"
        f"line_spacing=15"
    )

    cmd = [
        'ffmpeg', '-y',
        '-loop', '1', '-i', frame_path,
        '-i', audio_path,
        '-filter_complex',
        f"[0:v]scale={width}:{height},format=yuv420p,{drawtext_filter}[v]",
        '-map', '[v]',
        '-map', '1:a',
        '-c:v', 'h264_nvenc', '-preset', 'p5',
        '-c:a', 'aac', '-b:a', '192k', '-ac', '2',
        '-r', str(fps),
        '-t', str(duration),
        '-shortest',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  FFmpeg error: {result.stderr[-500:]}")
    return result.returncode == 0


def concatenate_three_parts(part1: str, insert: str, part2: str, output: str) -> bool:
    """Concatenate: opening clip + AI insert + rest of clip."""
    cmd = [
        'ffmpeg', '-y',
        '-i', part1,
        '-i', insert,
        '-i', part2,
        '-filter_complex',
        '[0:v][0:a][1:v][1:a][2:v][2:a]concat=n=3:v=1:a=1[outv][outa]',
        '-map', '[outv]',
        '-map', '[outa]',
        '-c:v', 'h264_nvenc', '-preset', 'p5',
        '-c:a', 'aac', '-b:a', '192k',
        output
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  FFmpeg concat error: {result.stderr[-500:]}")
    return result.returncode == 0


def transform_clip(input_video: str, output_video: str, creator: str):
    """Main transformation pipeline."""

    print(f"Transforming: {input_video}")
    print(f"Creator: {creator}")
    print()

    # Get original video properties
    props = get_video_properties(input_video)
    total_duration = get_video_duration(input_video)
    print(f"Original video: {props['width']}x{props['height']} @ {props['fps']:.2f}fps, {total_duration:.1f}s")

    # Determine split point (after intro, but not if video is too short)
    split_time = min(INTRO_DURATION, total_duration * 0.3)  # Max 30% of video
    print(f"AI insert will be placed at: {split_time:.1f}s")
    print()

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "audio.wav")
        voiceover_path = os.path.join(tmpdir, "voiceover.mp3")
        frame_path = os.path.join(tmpdir, "freeze_frame.jpg")
        part1_path = os.path.join(tmpdir, "part1.mp4")
        part2_path = os.path.join(tmpdir, "part2.mp4")
        insert_path = os.path.join(tmpdir, "ai_insert.mp4")

        # Step 1: Extract audio for transcription
        print("Step 1: Extracting audio...")
        if not extract_audio(input_video, audio_path):
            raise RuntimeError("Failed to extract audio")
        print("  Done.")

        # Step 2: Transcribe
        print("Step 2: Transcribing with Whisper API...")
        transcript = transcribe_audio(audio_path)
        print(f"  Transcript: {transcript[:200]}...")
        print()

        # Step 3: Generate hook
        print("Step 3: Generating hook with Claude...")
        hook = generate_hook(transcript, creator)
        print(f"  Hook: {hook}")
        print()

        # Step 4: Generate voiceover
        print("Step 4: Generating voiceover with ElevenLabs...")
        if not generate_voiceover(hook, voiceover_path):
            raise RuntimeError("Failed to generate voiceover")
        vo_duration = get_audio_duration(voiceover_path)
        print(f"  Done. Duration: {vo_duration:.2f}s")

        # Step 5: Split original video
        print(f"Step 5: Splitting video at {split_time:.1f}s...")
        if not split_video(input_video, split_time, part1_path, part2_path):
            raise RuntimeError("Failed to split video")
        print("  Done.")

        # Step 6: Extract freeze frame at split point
        print("Step 6: Extracting freeze frame...")
        if not extract_frame_at_time(input_video, split_time, frame_path):
            raise RuntimeError("Failed to extract frame")
        print("  Done.")

        # Step 7: Create AI insert segment
        print("Step 7: Creating AI insert with caption...")
        if not create_ai_insert(frame_path, voiceover_path, hook, insert_path,
                                props['width'], props['height'], props['fps'], tmpdir):
            raise RuntimeError("Failed to create AI insert")
        print("  Done.")

        # Step 8: Concatenate all three parts
        print("Step 8: Concatenating: opening + AI insert + rest...")
        if not concatenate_three_parts(part1_path, insert_path, part2_path, output_video):
            raise RuntimeError("Failed to concatenate")
        print("  Done.")

    final_duration = get_video_duration(output_video)
    print()
    print(f"SUCCESS! Output: {output_video}")
    print(f"Original duration: {total_duration:.1f}s -> Final duration: {final_duration:.1f}s")
    print(f"Added {vo_duration:.1f}s AI insert at {split_time:.1f}s mark")
    print(f"Hook: {hook}")


if __name__ == "__main__":
    # Test with one clip
    TEST_CLIP = r"C:\Users\asus\Desktop\projects\reeld\joeroganexperience\DC2cqFXzD1x.mp4"
    OUTPUT_CLIP = r"C:\Users\asus\Desktop\projects\reeld\test_transformed.mp4"
    CREATOR = "joeroganexperience"

    transform_clip(TEST_CLIP, OUTPUT_CLIP, CREATOR)
