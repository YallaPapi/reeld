"""
Reeld GUI - Complete video spoofing pipeline
Load JSON -> Download -> Spoof -> Generate CSV with Claude captions
"""

import json
import os
import re
import csv
import random
import string
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Optional: Claude API for caption rewriting
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# API key from environment variable
DEFAULT_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# CSV field names (matches template.csv)
FIELDNAMES = [
    "Text",
    "Pinterest Source Url",
    "LinkedIn Group Title",
    "CatalogId(optional)",
    "ProductIdsSeparatedByComma(optional)",
    "Source",
    "Image/Video link 1 (file path or URL(works only for images))",
]


class ReeldApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Reeld - Video Spoofer")
        self.root.geometry("650x650")
        self.root.resizable(False, False)

        # State
        self.input_json = tk.StringVar()
        self.output_folder = tk.StringVar()
        self.export_name = tk.StringVar(value="export")
        self.spoofs_per_video = tk.IntVar(value=2)
        self.use_claude = tk.BooleanVar(value=True)  # Default ON
        self.api_key = tk.StringVar(value=DEFAULT_API_KEY)
        self.is_running = False
        self.claude_client = None

        self.build_ui()

    def build_ui(self):
        # Main frame with padding
        main = ttk.Frame(self.root, padding=20)
        main.pack(fill=tk.BOTH, expand=True)

        # Input JSON
        ttk.Label(main, text="Input JSON (Apify scrape):").pack(anchor=tk.W)
        input_frame = ttk.Frame(main)
        input_frame.pack(fill=tk.X, pady=(0, 15))
        ttk.Entry(input_frame, textvariable=self.input_json, width=60).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(input_frame, text="Browse", command=self.browse_input).pack(side=tk.RIGHT, padx=(10, 0))

        # Output folder
        ttk.Label(main, text="Output folder:").pack(anchor=tk.W)
        output_frame = ttk.Frame(main)
        output_frame.pack(fill=tk.X, pady=(0, 15))
        ttk.Entry(output_frame, textvariable=self.output_folder, width=60).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(output_frame, text="Browse", command=self.browse_output).pack(side=tk.RIGHT, padx=(10, 0))

        # Export name
        ttk.Label(main, text="Export name:").pack(anchor=tk.W)
        ttk.Entry(main, textvariable=self.export_name, width=30).pack(anchor=tk.W, pady=(0, 15))

        # Spoofs per video
        ttk.Label(main, text="Spoofs per video:").pack(anchor=tk.W)
        spoof_frame = ttk.Frame(main)
        spoof_frame.pack(anchor=tk.W, pady=(0, 15))
        ttk.Spinbox(spoof_frame, from_=1, to=10, textvariable=self.spoofs_per_video, width=5).pack(side=tk.LEFT)
        ttk.Label(spoof_frame, text="variations per original video").pack(side=tk.LEFT, padx=(10, 0))

        # Claude checkbox + API key
        self.claude_checkbox = ttk.Checkbutton(main, text="Use Claude AI to rewrite captions",
                       variable=self.use_claude, command=self.toggle_api_key)
        self.claude_checkbox.pack(anchor=tk.W)

        self.api_key_frame = ttk.Frame(main)
        ttk.Label(self.api_key_frame, text="API Key:").pack(side=tk.LEFT)
        self.api_key_entry = ttk.Entry(self.api_key_frame, textvariable=self.api_key, width=55, show="*")
        self.api_key_entry.pack(side=tk.LEFT, padx=(10, 0))
        # Show by default since use_claude is True
        self.api_key_frame.pack(fill=tk.X, pady=(5, 15))

        # Progress section
        ttk.Separator(main, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        self.status_label = ttk.Label(main, text="Ready", font=("", 10, "bold"))
        self.status_label.pack(anchor=tk.W)

        self.progress_bar = ttk.Progressbar(main, mode='determinate', length=610)
        self.progress_bar.pack(fill=tk.X, pady=(5, 5))

        self.detail_label = ttk.Label(main, text="", foreground="gray")
        self.detail_label.pack(anchor=tk.W)

        # Log area
        log_frame = ttk.Frame(main)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 10))

        self.log_text = tk.Text(log_frame, height=12, width=75, state=tk.DISABLED, font=("Consolas", 9))
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Start button
        self.start_btn = ttk.Button(main, text="Start Processing", command=self.start_processing)
        self.start_btn.pack(pady=(10, 0))

    def browse_input(self):
        path = filedialog.askopenfilename(
            title="Select Apify JSON file",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if path:
            self.input_json.set(path)

    def browse_output(self):
        path = filedialog.askdirectory(title="Select output folder")
        if path:
            self.output_folder.set(path)

    def toggle_api_key(self):
        if self.use_claude.get():
            self.api_key_frame.pack(fill=tk.X, pady=(5, 15), after=self.claude_checkbox)
        else:
            self.api_key_frame.pack_forget()

    def log(self, msg):
        def _log():
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        self.root.after(0, _log)

    def update_status(self, status, detail=""):
        def _update():
            self.status_label.config(text=status)
            self.detail_label.config(text=detail)
        self.root.after(0, _update)

    def update_progress(self, value, maximum=100):
        def _update():
            self.progress_bar['maximum'] = maximum
            self.progress_bar['value'] = value
        self.root.after(0, _update)

    def start_processing(self):
        if self.is_running:
            return

        # Validate inputs
        if not self.input_json.get():
            messagebox.showerror("Error", "Please select an input JSON file")
            return
        if not self.output_folder.get():
            messagebox.showerror("Error", "Please select an output folder")
            return
        if not self.export_name.get():
            messagebox.showerror("Error", "Please enter an export name")
            return

        # Validate Claude API key if enabled
        if self.use_claude.get():
            if not ANTHROPIC_AVAILABLE:
                messagebox.showerror("Error", "anthropic package not installed. Run: pip install anthropic")
                return
            if not self.api_key.get():
                messagebox.showerror("Error", "Please enter your Claude API key")
                return
            try:
                self.claude_client = anthropic.Anthropic(api_key=self.api_key.get())
            except Exception as e:
                messagebox.showerror("Error", f"Invalid API key: {e}")
                return

        self.is_running = True
        self.start_btn.config(state=tk.DISABLED)

        # Run in thread to keep UI responsive
        thread = threading.Thread(target=self.run_pipeline, daemon=True)
        thread.start()

    def run_pipeline(self):
        try:
            # Clear log
            self.root.after(0, lambda: self.log_text.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.log_text.delete(1.0, tk.END))
            self.root.after(0, lambda: self.log_text.config(state=tk.DISABLED))

            # Setup paths
            base_output = os.path.join(self.output_folder.get(), self.export_name.get())
            downloads_dir = os.path.join(base_output, "downloads")
            spoofed_dir = os.path.join(base_output, "spoofed")
            os.makedirs(downloads_dir, exist_ok=True)
            os.makedirs(spoofed_dir, exist_ok=True)

            # Step 1: Load JSON
            self.update_status("Step 1/4: Loading JSON...")
            self.log(f"Loading: {self.input_json.get()}")
            with open(self.input_json.get(), 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.log(f"Loaded {len(data)} entries")

            # Build caption index from input JSON
            caption_index = {}
            tasks = []
            for item in data:
                shortcode = item.get('shortCode', '')
                caption = item.get('caption', '')
                input_url = item.get('inputUrl', '')
                video_url = item.get('videoUrl', '')

                match = re.search(r'instagram\.com/([^/]+)', input_url)
                user = match.group(1) if match else item.get('ownerUsername', 'unknown')

                if shortcode:
                    caption_index[shortcode] = {'caption': caption, 'user': user}

                if video_url and shortcode:
                    tasks.append({
                        'user': user,
                        'shortcode': shortcode,
                        'video_url': video_url,
                        'caption': caption
                    })

            self.log(f"Built caption index: {len(caption_index)} shortcodes")
            self.log(f"Found {len(tasks)} videos to download")

            # Save caption index
            caption_index_path = os.path.join(base_output, "captions_index.json")
            with open(caption_index_path, 'w', encoding='utf-8') as f:
                json.dump(caption_index, f, indent=2)
            self.log(f"Saved caption index: {caption_index_path}")

            # Step 2: Download videos
            self.update_status("Step 2/4: Downloading videos...", f"0/{len(tasks)}")
            downloaded = self.download_videos(tasks, downloads_dir)
            self.log(f"Downloaded {len(downloaded)} videos")

            if not downloaded:
                self.log("ERROR: No videos downloaded!")
                self.finish_pipeline(success=False)
                return

            # Step 3: Spoof videos
            self.update_status("Step 3/4: Spoofing videos...")
            spoofed, mapping = self.spoof_videos(downloaded, spoofed_dir)
            self.log(f"Created {len(spoofed)} spoofed videos")

            # Save spoofed mapping
            mapping_path = os.path.join(base_output, "spoofed_mapping.json")
            with open(mapping_path, 'w', encoding='utf-8') as f:
                json.dump(mapping, f, indent=2)
            self.log(f"Saved mapping: {mapping_path}")

            if not spoofed:
                self.log("ERROR: No videos spoofed!")
                self.finish_pipeline(success=False)
                return

            # Step 4: Generate CSV with Claude captions
            self.update_status("Step 4/4: Generating CSV...")
            csv_path = os.path.join(base_output, f"{self.export_name.get()}.csv")
            self.generate_csv(spoofed, caption_index, csv_path, base_output)

            # Done
            self.update_status("Complete!", f"Output: {base_output}")
            self.update_progress(100, 100)
            self.log(f"\n{'='*50}")
            self.log(f"DONE!")
            self.log(f"{'='*50}")
            self.log(f"Downloads: {downloads_dir}")
            self.log(f"Spoofed: {spoofed_dir}")
            self.log(f"CSV: {csv_path}")
            self.log(f"Mapping: {mapping_path}")
            self.log(f"Caption Index: {caption_index_path}")

            self.finish_pipeline(success=True)

        except Exception as e:
            import traceback
            self.log(f"ERROR: {str(e)}")
            self.log(traceback.format_exc())
            self.update_status("Error!", str(e))
            self.finish_pipeline(success=False)

    def download_videos(self, tasks, output_dir):
        """Download videos using yt-dlp"""
        downloaded = []
        total = len(tasks)

        def download_one(task, idx):
            user = task['user']
            shortcode = task['shortcode']
            video_url = task['video_url']

            user_dir = os.path.join(output_dir, user)
            os.makedirs(user_dir, exist_ok=True)
            output_path = os.path.join(user_dir, f"{shortcode}.mp4")

            if os.path.exists(output_path):
                return {'path': output_path, 'task': task, 'status': 'exists'}

            try:
                result = subprocess.run(
                    ['yt-dlp', '-o', output_path, video_url],
                    capture_output=True, text=True, timeout=120
                )
                if result.returncode == 0:
                    return {'path': output_path, 'task': task, 'status': 'downloaded'}
                else:
                    return {'path': None, 'task': task, 'status': 'failed', 'error': result.stderr[:200]}
            except Exception as e:
                return {'path': None, 'task': task, 'status': 'error', 'error': str(e)}

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(download_one, task, i): i for i, task in enumerate(tasks)}
            completed = 0

            for future in as_completed(futures):
                result = future.result()
                completed += 1

                if result['path']:
                    downloaded.append(result)
                    self.log(f"[{completed}/{total}] OK {result['task']['user']}/{result['task']['shortcode']}")
                else:
                    self.log(f"[{completed}/{total}] FAIL {result['task']['shortcode']}: {result.get('error', 'unknown')[:50]}")

                self.update_status("Step 2/4: Downloading videos...", f"{completed}/{total}")
                self.update_progress(completed, total)

        return downloaded

    def spoof_videos(self, downloaded, output_dir):
        """Spoof videos with randomized parameters"""
        spoofed = []
        mapping = []
        spoofs_per = self.spoofs_per_video.get()

        # Build task list
        spoof_tasks = []
        for item in downloaded:
            input_path = item['path']
            task = item['task']
            user = task['user']
            shortcode = task['shortcode']

            user_dir = os.path.join(output_dir, user)
            os.makedirs(user_dir, exist_ok=True)

            for variant in range(1, spoofs_per + 1):
                output_path = os.path.join(user_dir, f"{shortcode}-{variant}.mp4")
                spoof_tasks.append({
                    'input': input_path,
                    'output': output_path,
                    'task': task,
                    'variant': variant
                })

        total = len(spoof_tasks)
        self.log(f"Creating {total} spoofed videos ({spoofs_per} per original)")

        def spoof_one(spoof_task, idx):
            input_path = spoof_task['input']
            output_path = spoof_task['output']

            if os.path.exists(output_path):
                return {'output': output_path, 'input': input_path, 'task': spoof_task['task'],
                        'variant': spoof_task['variant'], 'status': 'exists'}

            try:
                # Get duration
                probe_cmd = [
                    'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                    '-show_entries', 'stream=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1', input_path
                ]
                result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
                duration = float(result.stdout.strip()) if result.stdout.strip() else 10.0

                # Random parameters (matching spoof_videos.py)
                w_keep = random.uniform(0.93, 0.97)  # 3-7% crop
                h_keep = random.uniform(0.95, 0.98)  # 2-5% crop
                trim_pct = random.uniform(0.03, 0.08)
                action = random.choice(['trim', 'extend'])
                v_bitrate = random.randint(3000, 17000)
                a_bitrate = random.randint(128, 264)
                scale_factor = random.choice([1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0])
                encoder_tag = random.choice(['Lavf58.76.100', 'Lavf60.3.100', 'Lavf62.6.100'])
                level = random.choice(['3.0', '3.1'])

                # Calculate duration modification
                if action == 'trim':
                    new_duration = max(duration * (1 - trim_pct), 0.1)
                    tpad = ""
                else:
                    new_duration = duration
                    extend = duration * trim_pct
                    tpad = f",tpad=stop_mode=clone:stop_duration={extend:.3f}"

                # Build filter
                crop_filter = f"crop=iw*{w_keep:.4f}:ih*{h_keep:.4f}:(iw-iw*{w_keep:.4f})/2:(ih-ih*{h_keep:.4f})/2"
                scale_filter = f"scale=trunc(iw*{scale_factor:.1f}/2)*2:trunc(ih*{scale_factor:.1f}/2)*2:flags=lanczos"
                vf = f"{crop_filter},{scale_filter}{tpad}"

                # Random metadata
                days_ago = random.randint(1, 730)
                creation_time = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
                cameras = ["iPhone 14 Pro", "iPhone 13", "Samsung Galaxy S23", "Pixel 7", "iPhone 15"]

                # FFmpeg command (NVENC GPU encoding)
                cmd = [
                    'ffmpeg', '-y',
                    '-i', input_path,
                    '-t', f'{new_duration:.3f}',
                    '-vf', vf,
                    '-c:v', 'h264_nvenc',
                    '-preset', 'p5',
                    '-tune', 'hq',
                    '-bf', '0',
                    '-g', '250',
                    '-pix_fmt', 'yuv420p',
                    '-b:v', f'{v_bitrate}k',
                    '-maxrate', f'{v_bitrate}k',
                    '-bufsize', f'{v_bitrate * 2}k',
                    '-c:a', 'aac',
                    '-b:a', f'{a_bitrate}k',
                    '-movflags', '+faststart',
                    '-metadata', f'encoder={encoder_tag}',
                    '-metadata', f'creation_time={creation_time}',
                    '-metadata', f'model={random.choice(cameras)}',
                    output_path
                ]

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

                if result.returncode == 0:
                    return {'output': output_path, 'input': input_path, 'task': spoof_task['task'],
                            'variant': spoof_task['variant'], 'status': 'spoofed',
                            'params': {
                                'crop_w_pct': round(100 * (1 - w_keep), 2),
                                'crop_h_pct': round(100 * (1 - h_keep), 2),
                                'action': action,
                                'trim_pct': round(trim_pct, 4),
                                'scale_factor': scale_factor,
                                'v_bitrate_k': v_bitrate,
                                'a_bitrate_k': a_bitrate,
                                'encoder': encoder_tag
                            }}
                else:
                    return {'output': None, 'task': spoof_task['task'], 'status': 'failed',
                            'error': result.stderr[-300:] if result.stderr else 'unknown'}

            except Exception as e:
                return {'output': None, 'task': spoof_task['task'], 'status': 'error', 'error': str(e)}

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(spoof_one, task, i): i for i, task in enumerate(spoof_tasks)}
            completed = 0

            for future in as_completed(futures):
                result = future.result()
                completed += 1

                if result.get('output'):
                    spoofed.append(result)
                    mapping.append({'input': result['input'], 'output': result['output']})
                    self.log(f"[{completed}/{total}] OK {Path(result['output']).name}")
                else:
                    self.log(f"[{completed}/{total}] FAIL: {result.get('error', 'unknown')[:50]}")

                self.update_status("Step 3/4: Spoofing videos...", f"{completed}/{total}")
                self.update_progress(completed, total)

        return spoofed, mapping

    def rewrite_caption_claude(self, caption, username, variant_idx):
        """Rewrite caption using Claude API"""
        if not caption or not caption.strip():
            return ""

        try:
            resp = self.claude_client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=400,
                messages=[{
                    "role": "user",
                    "content": (
                        f"This is variant #{variant_idx} - create a COMPLETELY UNIQUE caption. "
                        "Do NOT use the same sentence structure or opening as other variants. "
                        "Use different hooks, angles, and framing each time.\n\n"
                        f"Rewrite this Instagram caption for a clips account. Original creator: @{username}\n"
                        "Requirements:\n"
                        f"- Must credit @{username} naturally in the caption\n"
                        "- Write in 3rd person\n"
                        "- Keep it engaging and concise\n"
                        "- Use a completely different approach/style than typical variants\n"
                        "- ONLY 4-7 hashtags maximum, pick the most relevant ones\n"
                        "- ALL hashtags must be lowercase (e.g. #podcast not #Podcast)\n"
                        "- Caption text should be natural case, not all caps\n"
                        "- DO NOT change or mix up any names mentioned in the original caption\n"
                        "- Keep the same people/subjects as the original (don't confuse Tom with Tim, etc.)\n"
                        "- Only output the caption, nothing else\n\n"
                        f"Original caption: {caption}"
                    ),
                }],
            )
            return resp.content[0].text.strip()
        except Exception as e:
            self.log(f"Claude API error: {e}")
            return caption  # Return original on error

    def generate_csv(self, spoofed, caption_index, csv_path, base_output):
        """Generate final CSV with video paths and Claude-rewritten captions"""

        # Track variants per shortcode
        variant_counter = {}
        rows = []
        total = len(spoofed)

        self.log(f"Generating CSV for {total} videos...")
        if self.use_claude.get():
            self.log("Using Claude API to rewrite captions (10 parallel workers)...")

        def process_one(item, idx):
            output_path = item['output']
            task = item['task']
            shortcode = task['shortcode']
            user = task['user']

            # Get caption from index
            meta = caption_index.get(shortcode, {})
            caption = meta.get('caption', task.get('caption', ''))

            # Count variant
            variant_idx = variant_counter.get(shortcode, 0) + 1
            variant_counter[shortcode] = variant_idx

            # Rewrite caption
            if self.use_claude.get() and self.claude_client and caption:
                new_caption = self.rewrite_caption_claude(caption, user, variant_idx)
            else:
                # Simple fallback
                if caption:
                    new_caption = f"@{user}: {caption}"
                else:
                    new_caption = f"@{user}"

            return {
                "Text": new_caption,
                "Pinterest Source Url": "",
                "LinkedIn Group Title": "",
                "CatalogId(optional)": "catalogId=",
                "ProductIdsSeparatedByComma(optional)": "productIds=",
                "Source": "Manual",
                "Image/Video link 1 (file path or URL(works only for images))": output_path,
            }

        # Process with parallel workers for Claude API calls
        if self.use_claude.get() and self.claude_client:
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(process_one, item, i): i for i, item in enumerate(spoofed)}
                completed = 0

                for future in as_completed(futures):
                    row = future.result()
                    if row:
                        rows.append(row)
                    completed += 1

                    if completed % 5 == 0 or completed == total:
                        self.update_status("Step 4/4: Generating CSV...", f"Rewriting captions: {completed}/{total}")
                        self.update_progress(completed, total)
                        self.log(f"Caption progress: {completed}/{total}")
        else:
            # Sequential processing without Claude
            for idx, item in enumerate(spoofed):
                row = process_one(item, idx)
                if row:
                    rows.append(row)

        # Write master CSV
        self.log(f"Writing master CSV: {len(rows)} rows -> {csv_path}")
        # Use UTF-8 with BOM so Excel/Windows tools preserve emojis/special chars
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)

        # Write chunked CSVs (~4500 rows each)
        chunk_size = 4500
        if len(rows) > chunk_size:
            self.log(f"Writing chunked CSVs (~{chunk_size} rows each)...")
            for i in range(0, len(rows), chunk_size):
                chunk = rows[i:i + chunk_size]
                chunk_num = (i // chunk_size) + 1
                chunk_path = os.path.join(base_output, f"{self.export_name.get()}_part_{chunk_num:03d}.csv")
                with open(chunk_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                    writer.writeheader()
                    writer.writerows(chunk)
                self.log(f"  - {Path(chunk_path).name}: {len(chunk)} rows")

        self.log(f"CSV generation complete!")

    def finish_pipeline(self, success):
        def _finish():
            self.is_running = False
            self.start_btn.config(state=tk.NORMAL)
            if success:
                messagebox.showinfo("Complete", "Processing finished successfully!")
            else:
                messagebox.showerror("Error", "Processing failed. Check log for details.")
        self.root.after(0, _finish)


def main():
    root = tk.Tk()
    app = ReeldApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
