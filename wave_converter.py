import os
import subprocess
import random
from pathlib import Path

# Set up directories
input_folder = Path("audioData")
songs_folder = Path("audioData/songs")
clips_folder = Path("audioData/clips")

songs_folder.mkdir(exist_ok=True)
clips_folder.mkdir(exist_ok=True)

# Helper to get duration of the wav file using ffprobe
def get_audio_duration(file_path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(file_path)
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return float(result.stdout.strip())

# Helper to find next available songN.wav filename
def get_next_song_filename(folder):
    index = 1
    while True:
        candidate = folder / f"song{index}.wav"
        if not candidate.exists():
            return candidate, index
        index += 1

# Step 1: Convert MP3 to WAV and rename
mp3_files = list(input_folder.glob("*.mp3"))

if not mp3_files:
    print("No MP3 files found in audioData/")
else:
    for mp3_file in mp3_files:
        print(f"\n[INFO] Processing file: {mp3_file.name}")

        wav_path, song_index = get_next_song_filename(songs_folder)

        print(f"[INFO] Converting to: {wav_path.name}")

        # Convert MP3 to WAV using ffmpeg
        subprocess.run([
            "ffmpeg", "-y", "-i", str(mp3_file), str(wav_path)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Step 2: Extract 10s random clip
        duration = get_audio_duration(wav_path)
        print(f"[INFO] Duration of {wav_path.name}: {duration:.2f} seconds")

        if duration <= 10:
            start_time = 0
            print(f"[INFO] Duration too short for random clipping, using start_time = 0")
        else:
            start_time = random.uniform(0, duration - 10)
            print(f"[INFO] Random clip start time: {start_time:.2f} seconds")

        clip_filename = f"song{song_index}_clip1.wav"
        clip_path = clips_folder / clip_filename

        print(f"[INFO] Saving 10s clip to: {clip_filename}")

        subprocess.run([
            "ffmpeg", "-y", "-i", str(wav_path),
            "-ss", str(start_time), "-t", "10",
            str(clip_path)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print("\n✅ All files converted and clipped successfully.")
