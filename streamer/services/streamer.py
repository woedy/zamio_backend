import ffmpeg
import os
import time
from datetime import datetime
from pathlib import Path

STREAM_DIR = Path("radio_segments")

def ensure_output_dir():
    STREAM_DIR.mkdir(parents=True, exist_ok=True)

def get_timestamped_filename(station_name):
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    return STREAM_DIR / f"{station_name}_{timestamp}.wav"

def record_segment(stream_url, station_name, duration=10):
    ensure_output_dir()
    out_file = get_timestamped_filename(station_name)
    
    (
        ffmpeg
        .input(stream_url, t=duration)
        .output(str(out_file), format='wav', acodec='pcm_s16le', ac=1, ar='44100')
        .overwrite_output()
        .run(quiet=True)
    )
    
    return out_file
