"""
Create super mini chunks for VAs (5 videos + 5 captions each)
Reads with csv module but writes raw to preserve exact format
"""
import os
import csv
import shutil
from pathlib import Path
from collections import defaultdict


def format_csv_row(row):
    """Format a row exactly like the original CSV - quote only when needed"""
    parts = []
    for value in row:
        # Quote if contains comma, newline, or quote
        if ',' in value or '\n' in value or '\r' in value or '"' in value:
            # Escape quotes by doubling them
            escaped = value.replace('"', '""')
            parts.append(f'"{escaped}"')
        else:
            parts.append(value)
    return ','.join(parts)


def main():
    num_vas = 5
    videos_per_va = 3

    # Read source CSV with csv module (handles multiline properly)
    all_rows = []
    header = None

    for sub in ['b', 'c']:
        csv_file = Path(f"chunk_01{sub}.csv")
        if csv_file.exists():
            print(f"Reading {csv_file}...")
            with open(csv_file, "r", encoding="utf-8", newline='') as f:
                reader = csv.reader(f)
                file_header = next(reader)
                if header is None:
                    header = file_header
                for row in reader:
                    if row:
                        all_rows.append(row)

    print(f"Loaded {len(all_rows)} rows from chunk 1 sub-chunks")

    # Group by creator (video path is last field)
    rows_by_creator = defaultdict(list)
    for row in all_rows:
        video_path = row[-1]  # Last field is video path
        if "\\spoofed\\" in video_path:
            parts = video_path.split("\\spoofed\\")[1].split("\\")
            creator = parts[0] if parts else "unknown"
        elif "/spoofed/" in video_path:
            parts = video_path.split("/spoofed/")[1].split("/")
            creator = parts[0] if parts else "unknown"
        else:
            creator = "unknown"
        rows_by_creator[creator].append(row)

    creators = list(rows_by_creator.keys())
    print(f"Found {len(creators)} creators")

    # Distribute evenly: round-robin across creators
    total_needed = num_vas * videos_per_va
    selected_rows = []
    creator_idx = 0
    creator_offsets = {c: 0 for c in creators}

    while len(selected_rows) < total_needed:
        creator = creators[creator_idx % len(creators)]
        offset = creator_offsets[creator]

        if offset < len(rows_by_creator[creator]):
            selected_rows.append(rows_by_creator[creator][offset])
            creator_offsets[creator] += 1

        creator_idx += 1
        if creator_idx > len(creators) * 100:
            break

    print(f"Selected {len(selected_rows)} videos for {num_vas} VAs\n")

    # Create VA chunks
    for va_num in range(1, num_vas + 1):
        va_dir = Path(f"va_chunk_{va_num:02d}")

        if va_dir.exists():
            shutil.rmtree(va_dir)
        va_dir.mkdir()

        # Get this VA's rows
        start_idx = (va_num - 1) * videos_per_va
        end_idx = start_idx + videos_per_va
        va_rows = selected_rows[start_idx:end_idx]

        print(f"VA {va_num}: Creating {va_dir}/")

        # Copy videos and collect valid rows
        valid_rows = []
        for row in va_rows:
            video_path = row[-1]

            if os.path.exists(video_path):
                filename = os.path.basename(video_path)
                new_path = va_dir / filename
                shutil.copy2(video_path, new_path)
                valid_rows.append(row)
                print(f"  - {filename}")

        # Write CSV - format manually to match original exactly
        csv_out = va_dir / f"va_chunk_{va_num:02d}.csv"
        with open(csv_out, "w", encoding="utf-8", newline='') as f:
            # Write header
            f.write(format_csv_row(header) + '\r\n')
            # Write rows
            for row in valid_rows:
                f.write(format_csv_row(row) + '\r\n')

        print(f"  Created {csv_out}\n")

    print(f"Done! Created {num_vas} VA chunks with {videos_per_va} videos each")


if __name__ == "__main__":
    main()
