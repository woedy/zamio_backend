import os
import subprocess
import uuid

from .models import Song, Fingerprint
from .engine import fingerprint

def generate_fingerprints_for_song(song_id):
    # Fetch the uploaded song
    song = Song.objects.get(id=song_id)
    original_path = song.audio_file.path

    # Convert original file to temporary WAV using FFmpeg
    wav_path = convert_to_wav_ffmpeg(original_path, output_dir=os.path.dirname(original_path))
    if not wav_path:
        print(f"[ERROR] FFmpeg failed to convert: {original_path}")
        return

    try:
        # Read WAV file into numpy array
        samples, rate = read_wav_as_array(wav_path)

        # Generate audio fingerprints
        hashes = fingerprint(samples, Fs=rate)

        # Store fingerprints in the DB
        fingerprint_objects = [
            Fingerprint(song=song, hash=h, offset=o)
            for h, o in hashes
        ]
        Fingerprint.objects.bulk_create(fingerprint_objects)

        print(f"[INFO] Fingerprinted '{song.title}' with {len(hashes)} hashes.")
    except Exception as e:
        print(f"[ERROR] Fingerprinting failed: {e}")
    finally:
        # Clean up the temporary WAV file
        if os.path.exists(wav_path):
            os.remove(wav_path)

def convert_to_wav_ffmpeg(input_path, output_dir=None):
    if not output_dir:
        output_dir = os.path.dirname(input_path)

    output_filename = f"{uuid.uuid4().hex}.wav"
    output_path = os.path.join(output_dir, output_filename)

    command = [
        "ffmpeg",
        "-y",  # overwrite if exists
        "-i", input_path,  # input file
        "-ac", "1",         # mono
        "-ar", "44100",     # sample rate: 44.1 kHz
        "-f", "wav",        # force WAV output
        output_path
    ]

    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_path
    except subprocess.CalledProcessError:
        print(f"[ERROR] FFmpeg failed to convert {input_path}")
        return None








import wave
import numpy as np

def read_wav_as_array(path: str):
    with wave.open(path, 'rb') as wf:
        channels = wf.getnchannels()
        frames = wf.readframes(wf.getnframes())
        framerate = wf.getframerate()

        # 16-bit PCM assumed
        samples = np.frombuffer(frames, dtype=np.int16)

        if channels > 1:
            # More accurate downmixing for stereo
            samples = samples.reshape(-1, channels).mean(axis=1).astype(np.int16)

        return samples, framerate








def extract_fingerprints(file_path):
    try:
        # Read file into samples and sample rate
        samples, sr = read_wav_as_array(file_path)

        # Use the same fingerprinting engine used for DB songs
        fingerprints = fingerprint(samples, Fs=sr)

        return fingerprints

    except Exception as e:
        print(f"[ERROR] Failed to extract fingerprints: {e}")
        return []