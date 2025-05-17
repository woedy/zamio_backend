import nbformat
from nbformat import v4 as nbf

# Paste your entire notebook script here as a single multiline string
notebook_script = '''# %% [markdown]
# # Audio Fingerprinting and Matching Demo with Bayesian Optimization
#
# This Jupyter notebook demonstrates **audio fingerprinting** and **audio matching** for the **RadioPlay** royalty payment system, designed to monitor radio plays for Ghanaian artists. The system identifies songs from 10-second audio clips, similar to Shazam, by generating unique fingerprints and matching them against a database. This demo allows you to:
#
# - Generate fingerprints from audio files (full songs and clips).
# - Visualize spectrograms, waveforms, and detected peaks.
# - Automatically find the best parameter configuration for peak detection and matching, optimized for Ghanaian music, using Bayesian optimization.
# - Match clips against a song database.
#
# ## Prerequisites
#
# - **Audio Files**: Place one full song (WAV) and a 10-second clip (WAV) in a ./audio folder. Example: `song1.wav`, `clip1.wav`.
# - **Dependencies**: Install required Python packages, including `optuna` for Bayesian optimization.
# - **Environment**: Run in a Jupyter notebook with access to ffmpeg for audio processing.
#
# ## Setup
#
# Install dependencies and create an audio folder:

# %%
!pip install librosa numba xxhash matplotlib numpy scipy pandas optuna
!mkdir -p ./audio
# Convert MP3 to WAV if needed: ffmpeg -i ./audio/song1.mp3 ./audio/song1.wav
# Example clip extraction: ffmpeg -i ./audio/song1.wav -ss 60 -t 10 -c copy ./audio/clip1.wav

# %% [markdown]
# ## Step 1: Define Fingerprinting Engine
#
# We use a fingerprinting engine based on librosa for spectrograms, numba for fast peak detection, and xxhash for hashing.
#
# **Modifications**:
# - Enhanced logging for peaks and hashes.
# - Configurable parameters for optimization, tailored for Ghanaian music.

# %%
import numpy as np
import librosa
import librosa.display
import matplotlib.pyplot as plt
from numba import jit
import xxhash
from operator import itemgetter
import logging
from typing import List, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
CONFIG = {
    'DEFAULT_FS': 44100,
    'DEFAULT_WINDOW_SIZE': 2048,
    'DEFAULT_OVERLAP_RATIO': 0.5,
    'DEFAULT_FAN_VALUE': 15,
    'DEFAULT_AMP_MIN': -20,
    'PEAK_NEIGHBORHOOD_SIZE': 10,
    'MIN_HASH_TIME_DELTA': 0,
    'MAX_HASH_TIME_DELTA': 500,
    'FINGERPRINT_REDUCTION': 20,
    'PEAK_SORT': True
}

def fingerprint(channel_samples: np.ndarray, Fs: int = CONFIG['DEFAULT_FS'], 
                wsize: int = CONFIG['DEFAULT_WINDOW_SIZE'], wratio: float = CONFIG['DEFAULT_OVERLAP_RATIO'],
                fan_value: int = CONFIG['DEFAULT_FAN_VALUE'], amp_min: float = CONFIG['DEFAULT_AMP_MIN'],
                peak_neighborhood_size: int = CONFIG['PEAK_NEIGHBORHOOD_SIZE'],
                min_hash_time_delta: int = CONFIG['MIN_HASH_TIME_DELTA'],
                max_hash_time_delta: int = CONFIG['MAX_HASH_TIME_DELTA'],
                fingerprint_reduction: int = CONFIG['FINGERPRINT_REDUCTION'],
                peak_sort: bool = CONFIG['PEAK_SORT']) -> List[Tuple[str, int]]:
    """Generate fingerprints from audio samples."""
    try:
        samples = channel_samples.astype(np.float32) / 32768.0
        hop_length = int(wsize * (1 - wratio))
        S = librosa.stft(samples, n_fft=wsize, hop_length=hop_length, window='hann')
        arr2D = librosa.amplitude_to_db(np.abs(S), ref=np.max)
        logger.info(f"Spectrogram min: {arr2D.min():.2f}, max: {arr2D.max():.2f}")
        local_maxima = get_2D_peaks(arr2D, amp_min=amp_min, peak_neighborhood_size=peak_neighborhood_size)
        hashes = generate_hashes(local_maxima, fan_value=fan_value, 
                                min_hash_time_delta=min_hash_time_delta, 
                                max_hash_time_delta=max_hash_time_delta, 
                                fingerprint_reduction=fingerprint_reduction, 
                                peak_sort=peak_sort)
        logger.info(f"Generated {len(hashes)} fingerprints for {len(samples)/Fs:.2f}s audio")
        return hashes
    except Exception as e:
        logger.error(f"Fingerprinting failed: {e}")
        return []

@jit(nopython=True)
def get_2D_peaks_numba(arr2D: np.ndarray, amp_min: float, peak_neighborhood_size: int) -> List[Tuple[int, int]]:
    """Optimized peak detection with numba."""
    peaks = []
    rows, cols = arr2D.shape
    neighborhood_size = peak_neighborhood_size // 2
    for i in range(neighborhood_size, rows - neighborhood_size):
        for j in range(neighborhood_size, cols - neighborhood_size):
            if arr2D[i, j] > amp_min:
                is_max = True
                for di in range(-neighborhood_size, neighborhood_size + 1):
                    for dj in range(-neighborhood_size, neighborhood_size + 1):
                        if di == 0 and dj == 0:
                            continue
                        if arr2D[i + di, j + dj] > arr2D[i, j]:
                            is_max = False
                            break
                    if not is_max:
                        break
                if is_max:
                    peaks.append((i, j))
    return peaks

def get_2D_peaks(arr2D: np.ndarray, plot: bool = False, amp_min: float = CONFIG['DEFAULT_AMP_MIN'], 
                 peak_neighborhood_size: int = CONFIG['PEAK_NEIGHBORHOOD_SIZE']) -> List[Tuple[int, int]]:
    """Extract peaks from spectrogram."""
    try:
        peaks = get_2D_peaks_numba(arr2D, amp_min, peak_neighborhood_size)
        logger.info(f"Detected {len(peaks)} peaks with amp_min={amp_min}")
        if plot:
            plt.figure(figsize=(10, 6))
            plt.imshow(arr2D, origin='lower', aspect='auto', cmap='viridis')
            if peaks:
                freqs, times = zip(*peaks)
                plt.scatter(times, freqs, c='r', s=10, label='Peaks')
            plt.colorbar(label='Amplitude (dB)')
            plt.xlabel('Time (frames)')
            plt.ylabel('Frequency (bins)')
            plt.title(f'Spectrogram with Detected Peaks (amp_min={amp_min})')
            plt.legend()
            plt.show()
        return peaks
    except Exception as e:
        logger.error(f"Peak detection failed: {e}")
        return []

def generate_hashes(peaks: List[Tuple[int, int]], fan_value: int = CONFIG['DEFAULT_FAN_VALUE'],
                    min_hash_time_delta: int = CONFIG['MIN_HASH_TIME_DELTA'],
                    max_hash_time_delta: int = CONFIG['MAX_HASH_TIME_DELTA'],
                    fingerprint_reduction: int = CONFIG['FINGERPRINT_REDUCTION'],
                    peak_sort: bool = CONFIG['PEAK_SORT']) -> List[Tuple[str, int]]:
    """Generate hashes from peaks."""
    try:
        if peak_sort:
            peaks.sort(key=itemgetter(1))
        hashes = []
        valid_pairs = 0
        for i in range(len(peaks)):
            for j in range(1, fan_value):
                if (i + j) < len(peaks):
                    freq1 = peaks[i][0]
                    freq2 = peaks[i + j][0]
                    t1 = peaks[i][1]
                    t2 = peaks[i + j][1]
                    t_delta = t2 - t1
                    if min_hash_time_delta <= t_delta <= max_hash_time_delta:
                        valid_pairs += 1
                        h = xxhash.xxh64(f"{freq1}|{freq2}|{t_delta}".encode('utf-8'))
                        hash_str = h.hexdigest()[:fingerprint_reduction]
                        hashes.append((hash_str, t1))
        logger.info(f"Generated {valid_pairs} valid peak pairs for hashing")
        return hashes
    except Exception as e:
        logger.error(f"Hash generation failed: {e}")
        return []

# %% [markdown]
# ## Step 2: Load Audio Files
#
# Load a full song and a 10-second clip to simulate radio monitoring.
#
# **Modifications**:
# - Use WAV format for song (`song1.wav`).
# - Enhanced logging and waveform visualization.

# %%
import os

def load_audio(file_path: str) -> Tuple[np.ndarray, int]:
    """Load audio file and convert to int16."""
    try:
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return np.array([]), 0
        samples, sr = librosa.load(file_path, sr=CONFIG['DEFAULT_FS'], mono=True)
        samples = (samples * 32768).astype(np.int16)
        logger.info(f"Loaded {file_path}: {len(samples)} samples, {sr} Hz, max amplitude: {np.max(np.abs(samples))}")
        return samples, sr
    except Exception as e:
        logger.error(f"Failed to load {file_path}: {e}")
        return np.array([]), 0

# Audio files
song_path = './audio/song1.wav'  # Full song (WAV)
clip_path = './audio/clip1.wav'  # 10-second clip

song_samples, song_sr = load_audio(song_path)
clip_samples, clip_sr = load_audio(clip_path)

print(f"Loaded song: {len(song_samples)/song_sr:.2f}s, {song_sr} Hz")
print(f"Loaded clip: {len(clip_samples)/clip_sr:.2f}s, {clip_sr} Hz")

# Visualize clip waveform
if len(clip_samples) > 0:
    plt.figure(figsize=(10, 4))
    plt.plot(clip_samples)
    plt.title('Clip Waveform')
    plt.xlabel('Sample')
    plt.ylabel('Amplitude')
    plt.show()

# %% [markdown]
# ## Step 3: Define Song and Matching Functions
#
# Define the song model and matching logic.
#
# **Modifications**:
# - Separated song fingerprinting and matching for optimization.
# - Added new parameters for optimization.

# %%
# Simulate Django Song model
class Song:
    def __init__(self, id, title):
        self.id = id
        self.title = title

# Create a song entry
song = Song(id=1, title='Sample Song')

def generate_song_fingerprints(samples, sr, song_id, amp_min=CONFIG['DEFAULT_AMP_MIN'], 
                              peak_neighborhood_size=CONFIG['PEAK_NEIGHBORHOOD_SIZE'], 
                              fan_value=CONFIG['DEFAULT_FAN_VALUE'], 
                              wsize=CONFIG['DEFAULT_WINDOW_SIZE'], wratio=CONFIG['DEFAULT_OVERLAP_RATIO'],
                              min_hash_time_delta=CONFIG['MIN_HASH_TIME_DELTA'], 
                              max_hash_time_delta=CONFIG['MAX_HASH_TIME_DELTA'],
                              fingerprint_reduction=CONFIG['FINGERPRINT_REDUCTION'], 
                              peak_sort=CONFIG['PEAK_SORT'], plot=False):
    """Generate fingerprints for a song."""
    if len(samples) == 0:
        logger.error("No samples provided for fingerprinting")
        return []
    fingerprints = fingerprint(samples, Fs=sr, amp_min=amp_min, peak_neighborhood_size=peak_neighborhood_size, 
                              fan_value=fan_value, wsize=wsize, wratio=wratio, 
                              min_hash_time_delta=min_hash_time_delta, max_hash_time_delta=max_hash_time_delta,
                              fingerprint_reduction=fingerprint_reduction, peak_sort=peak_sort)
    db_fingerprints = [(song_id, h, o) for h, o in fingerprints]
    if plot:
        samples_float = samples.astype(np.float32) / 32768.0
        hop_length = int(wsize * (1 - wratio))
        S = librosa.stft(samples_float, n_fft=wsize, hop_length=hop_length, window='hann')
        arr2D = librosa.amplitude_to_db(np.abs(S), ref=np.max)
        get_2D_peaks(arr2D, plot=True, amp_min=amp_min, peak_neighborhood_size=peak_neighborhood_size)
    return db_fingerprints

from collections import Counter

def match_clip(clip_samples, clip_sr, db_fingerprints, amp_min=CONFIG['DEFAULT_AMP_MIN'], 
               fan_value=CONFIG['DEFAULT_FAN_VALUE'], peak_neighborhood_size=CONFIG['PEAK_NEIGHBORHOOD_SIZE'],
               min_match_count=10, min_input_conf=10.0, min_db_conf=2.0, 
               wsize=CONFIG['DEFAULT_WINDOW_SIZE'], wratio=CONFIG['DEFAULT_OVERLAP_RATIO'],
               min_hash_time_delta=CONFIG['MIN_HASH_TIME_DELTA'], 
               max_hash_time_delta=CONFIG['MAX_HASH_TIME_DELTA'],
               fingerprint_reduction=CONFIG['FINGERPRINT_REDUCTION'], 
               peak_sort=CONFIG['PEAK_SORT']):
    """Match clip fingerprints against database."""
    if len(clip_samples) == 0:
        return {"match": False, "reason": "No samples in clip"}
    
    # Visualize clip waveform
    plt.figure(figsize=(10, 4))
    plt.plot(clip_samples)
    plt.title('Clip Waveform')
    plt.xlabel('Sample')
    plt.ylabel('Amplitude')
    plt.show()
    
    # Compute spectrogram for visualization
    samples_float = clip_samples.astype(np.float32) / 32768.0
    hop_length = int(wsize * (1 - wratio))
    S = librosa.stft(samples_float, n_fft=wsize, hop_length=hop_length, window='hann')
    arr2D = librosa.amplitude_to_db(np.abs(S), ref=np.max)
    logger.info(f"Clip spectrogram min: {arr2D.min():.2f}, max: {arr2D.max():.2f}")
    
    # Generate clip fingerprints
    clip_fingerprints = fingerprint(clip_samples, Fs=clip_sr, amp_min=amp_min, fan_value=fan_value, 
                                    peak_neighborhood_size=peak_neighborhood_size, wsize=wsize, wratio=wratio,
                                    min_hash_time_delta=min_hash_time_delta, max_hash_time_delta=max_hash_time_delta,
                                    fingerprint_reduction=fingerprint_reduction, peak_sort=peak_sort)
    
    # Visualize spectrogram and peaks
    get_2D_peaks(arr2D, plot=True, amp_min=amp_min, peak_neighborhood_size=peak_neighborhood_size)
    
    if not clip_fingerprints:
        return {"match": False, "reason": "No fingerprints extracted", "hashes_matched": 0, 
                "input_confidence": 0.0, "db_confidence": 0.0}
    
    # Match fingerprints
    query_hashes = [h for h, _ in clip_fingerprints]
    db_hashes = {(h, o, song_id) for song_id, h, o in db_fingerprints if h in query_hashes}
    if not db_hashes:
        return {"match": False, "reason": "No matching hashes found", "hashes_matched": 0, 
                "input_confidence": 0.0, "db_confidence": 0.0}
    
    match_map = Counter()
    for h, query_offset in clip_fingerprints:
        for db_hash, db_offset, song_id in db_hashes:
            if h == db_hash:
                offset_diff = db_offset - query_offset
                match_map[(song_id, offset_diff)] += 1
    
    if not match_map:
        return {"match": False, "reason": "No offset alignment found", "hashes_matched": 0, 
                "input_confidence": 0.0, "db_confidence": 0.0}
    
    (song_id, offset_diff), match_count = match_map.most_common(1)[0]
    total_query_hashes = len(query_hashes)
    total_db_hashes = sum(1 for _, _, sid in db_fingerprints if sid == song_id)
    input_confidence = (match_count / total_query_hashes) * 100
    db_confidence = (match_count / total_db_hashes) * 100 if total_db_hashes else 0
    
    if match_count < min_match_count or input_confidence < min_input_conf or db_confidence < min_db_conf:
        return {
            "match": False,
            "reason": "Low confidence match",
            "hashes_matched": match_count,
            "input_confidence": input_confidence,
            "db_confidence": db_confidence
        }
    
    return {
        "match": True,
        "song_id": song_id,
        "offset": offset_diff,
        "hashes_matched": match_count,
        "input_confidence": input_confidence,
        "db_confidence": db_confidence
    }

# %% [markdown]
# ## Step 3.5: Bayesian Optimization for Optimal Parameters
#
# Use Bayesian optimization with optuna to find the best parameter configuration for fingerprinting and matching, optimized for Ghanaian music. This replaces the full grid search to reduce computational cost.
#
# **Metrics**:
# - Number of peaks detected (clip and song).
# - Number of fingerprints generated (clip and song).
# - Matching confidence (input_confidence, db_confidence).
# - Successful match (match: True).
#
# **Scoring**:
# - Score = (clip_fingerprints / max_clip_fingerprints) * 0.3 + (song_fingerprints / max_song_fingerprints) * 0.3 + input_confidence * 0.2 + db_confidence * 0.2 if match is True, else 0.

# %%
import pandas as pd
import optuna

# Define parameter ranges tailored for Ghanaian music
param_ranges = {
    'amp_min': (-30, -10),  # Focus on mid-to-high amplitude peaks for rhythmic clarity
    'peak_neighborhood_size': (5, 10),  # Smaller sizes for precise peak detection
    'fan_value': (10, 15),  # Moderate fan-out for rhythmic patterns
    'min_match_count': (5, 10),  # Lower thresholds for short clips
    'min_input_conf': (5.0, 10.0),  # Relaxed confidence for noisy radio clips
    'min_db_conf': (1.0, 2.0),  # Lower DB confidence for diverse song lengths
    'wsize': [1024, 2048],  # Smaller windows for rhythmic detail
    'wratio': (0.5, 0.75),  # Higher overlap for transient detection
    'min_hash_time_delta': (0, 5),  # Allow close peaks for fast rhythms
    'max_hash_time_delta': (200, 400),  # Shorter deltas for local features
    'fingerprint_reduction': [20],  # Fixed for consistency
    'peak_sort': [True]  # Fixed for deterministic hashes
}

# Function to compute fingerprints and match
def evaluate_params(song_samples, song_sr, clip_samples, clip_sr, song_id, params):
    amp_min = params['amp_min']
    peak_neighborhood_size = params['peak_neighborhood_size']
    fan_value = params['fan_value']
    min_match_count = params['min_match_count']
    min_input_conf = params['min_input_conf']
    min_db_conf = params['min_db_conf']
    wsize = params['wsize']
    wratio = params['wratio']
    min_hash_time_delta = params['min_hash_time_delta']
    max_hash_time_delta = params['max_hash_time_delta']
    fingerprint_reduction = params['fingerprint_reduction']
    peak_sort = params['peak_sort']
    
    # Generate song fingerprints
    song_fingerprints = generate_song_fingerprints(song_samples, song_sr, song_id, 
                                                  amp_min=amp_min, peak_neighborhood_size=peak_neighborhood_size, 
                                                  fan_value=fan_value, wsize=wsize, wratio=wratio, 
                                                  min_hash_time_delta=min_hash_time_delta, 
                                                  max_hash_time_delta=max_hash_time_delta, 
                                                  fingerprint_reduction=fingerprint_reduction, 
                                                  peak_sort=peak_sort, plot=False)
    
    # Generate clip fingerprints and match
    result = match_clip(clip_samples, clip_sr, song_fingerprints, 
                        amp_min=amp_min, fan_value=fan_value, peak_neighborhood_size=peak_neighborhood_size, 
                        min_match_count=min_match_count, min_input_conf=min_input_conf, min_db_conf=min_db_conf, 
                        wsize=wsize, wratio=wratio, min_hash_time_delta=min_hash_time_delta, 
                        max_hash_time_delta=max_hash_time_delta, fingerprint_reduction=fingerprint_reduction, 
                        peak_sort=peak_sort)
    
    # Compute metrics
    clip_peaks = 0
    clip_fingerprints = len([h for h, _ in fingerprint(clip_samples, Fs=clip_sr, amp_min=amp_min, 
                                                       fan_value=fan_value, peak_neighborhood_size=peak_neighborhood_size,
                                                       wsize=wsize, wratio=wratio, 
                                                       min_hash_time_delta=min_hash_time_delta, 
                                                       max_hash_time_delta=max_hash_time_delta, 
                                                       fingerprint_reduction=fingerprint_reduction, 
                                                       peak_sort=peak_sort)])
    song_peaks = 0
    song_fingerprints = len(song_fingerprints)
    
    # Compute score
    max_clip_fingerprints = clip_fingerprints if clip_fingerprints > 0 else 1
    max_song_fingerprints = song_fingerprints if song_fingerprints > 0 else 1
    score = (
        (clip_fingerprints / max_clip_fingerprints) * 0.3 +
        (song_fingerprints / max_song_fingerprints) * 0.3 +
        result.get('input_confidence', 0.0) * 0.2 +
        result.get('db_confidence', 0.0) * 0.2
    ) if result['match'] else 0
    
    return {
        'amp_min': amp_min,
        'peak_neighborhood_size': peak_neighborhood_size,
        'fan_value': fan_value,
        'min_match_count': min_match_count,
        'min_input_conf': min_input_conf,
        'min_db_conf': min_db_conf,
        'wsize': wsize,
        'wratio': wratio,
        'min_hash_time_delta': min_hash_time_delta,
        'max_hash_time_delta': max_hash_time_delta,
        'fingerprint_reduction': fingerprint_reduction,
        'peak_sort': peak_sort,
        'clip_peaks': clip_peaks,
        'clip_fingerprints': clip_fingerprints,
        'song_peaks': song_peaks,
        'song_fingerprints': song_fingerprints,
        'match': result['match'],
        'hashes_matched': result.get('hashes_matched', 0),
        'input_confidence': result.get('input_confidence', 0.0),
        'db_confidence': result.get('db_confidence', 0.0),
        'reason': result.get('reason', ''),
        'score': score
    }

# Define objective function for optuna
def objective(trial):
    params = {
        'amp_min': trial.suggest_float('amp_min', param_ranges['amp_min'][0], param_ranges['amp_min'][1]),
        'peak_neighborhood_size': trial.suggest_int('peak_neighborhood_size', param_ranges['peak_neighborhood_size'][0], param_ranges['peak_neighborhood_size'][1]),
        'fan_value': trial.suggest_int('fan_value', param_ranges['fan_value'][0], param_ranges['fan_value'][1]),
        'min_match_count': trial.suggest_int('min_match_count', param_ranges['min_match_count'][0], param_ranges['min_match_count'][1]),
        'min_input_conf': trial.suggest_float('min_input_conf', param_ranges['min_input_conf'][0], param_ranges['min_input_conf'][1]),
        'min_db_conf': trial.suggest_float('min_db_conf', param_ranges['min_db_conf'][0], param_ranges['min_db_conf'][1]),
        'wsize': trial.suggest_categorical('wsize', param_ranges['wsize']),
        'wratio': trial.suggest_float('wratio', param_ranges['wratio'][0], param_ranges['wratio'][1]),
        'min_hash_time_delta': trial.suggest_int('min_hash_time_delta', param_ranges['min_hash_time_delta'][0], param_ranges['min_hash_time_delta'][1]),
        'max_hash_time_delta': trial.suggest_int('max_hash_time_delta', param_ranges['max_hash_time_delta'][0], param_ranges['max_hash_time_delta'][1]),
        'fingerprint_reduction': trial.suggest_categorical('fingerprint_reduction', param_ranges['fingerprint_reduction']),
        'peak_sort': trial.suggest_categorical('peak_sort', param_ranges['peak_sort'])
    }
    result = evaluate_params(song_samples, song_sr, clip_samples, clip_sr, song.id, params)
    print(f"Trial {trial.number}: score={result['score']:.4f}, match={result['match']}, params={params}")
    return result['score']

# Run Bayesian optimization
study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=50)  # Adjust n_trials based on computational resources

# Collect results
results = [evaluate_params(song_samples, song_sr, clip_samples, clip_sr, song.id, trial.params) for trial in study.trials]

# Create DataFrame
df = pd.DataFrame(results)

# Find best configuration
best_config = df.loc[df['score'].idxmax()]
print("\nBest Configuration:")
print(best_config)

# Display results table
print("\nOptimization Results:")
print(df[['amp_min', 'peak_neighborhood_size', 'fan_value', 'min_match_count', 'min_input_conf', 'min_db_conf',
          'wsize', 'wratio', 'min_hash_time_delta', 'max_hash_time_delta', 'fingerprint_reduction', 'peak_sort',
          'clip_fingerprints', 'song_fingerprints', 'match', 'input_confidence', 'db_confidence', 'score', 'reason']])

# Visualize results
plt.figure(figsize=(12, 6))
for wsize in param_ranges['wsize']:
    subset = df[df['wsize'] == wsize]
    plt.scatter(subset['amp_min'], subset['input_confidence'], label=f'wsize={wsize}', alpha=0.6)
plt.xlabel('amp_min')
plt.ylabel('Input Confidence (%)')
plt.title('Input Confidence vs. amp_min by wsize')
plt.legend()
plt.grid(True)
plt.show()

plt.figure(figsize=(12, 6))
subset = df
plt.scatter(subset['wratio'], subset['clip_fingerprints'], label='All trials', alpha=0.6)
plt.xlabel('wratio')
plt.ylabel('Clip Fingerprints')
plt.title('Clip Fingerprints vs. wratio')
plt.legend()
plt.grid(True)
plt.show()

# %% [markdown]
# ## Step 4: Test Best Configuration
#
# Use the best configuration to generate fingerprints and match the clip.

# %%
# Extract best parameters
best_amp_min = best_config['amp_min']
best_peak_neighborhood_size = best_config['peak_neighborhood_size']
best_fan_value = best_config['fan_value']
best_min_match_count = best_config['min_match_count']
best_min_input_conf = best_config['min_input_conf']
best_min_db_conf = best_config['min_db_conf']
best_wsize = best_config['wsize']
best_wratio = best_config['wratio']
best_min_hash_time_delta = best_config['min_hash_time_delta']
best_max_hash_time_delta = best_config['max_hash_time_delta']
best_fingerprint_reduction = best_config['fingerprint_reduction']
best_peak_sort = best_config['peak_sort']

print(f"\nTesting Best Configuration: amp_min={best_amp_min}, peak_neighborhood_size={best_peak_neighborhood_size}, "
      f"fan_value={best_fan_value}, min_match_count={best_min_match_count}, min_input_conf={best_min_input_conf}, "
      f"min_db_conf={best_min_db_conf}, wsize={best_wsize}, wratio={best_wratio}, "
      f"min_hash_time_delta={best_min_hash_time_delta}, max_hash_time_delta={best_max_hash_time_delta}, "
      f"fingerprint_reduction={best_fingerprint_reduction}, peak_sort={best_peak_sort}")

# Generate song fingerprints with visualization
song_fingerprints = generate_song_fingerprints(song_samples, song_sr, song.id, 
                                              amp_min=best_amp_min, peak_neighborhood_size=best_peak_neighborhood_size, 
                                              fan_value=best_fan_value, wsize=best_wsize, wratio=best_wratio, 
                                              min_hash_time_delta=best_min_hash_time_delta, 
                                              max_hash_time_delta=best_max_hash_time_delta, 
                                              fingerprint_reduction=best_fingerprint_reduction, 
                                              peak_sort=best_peak_sort, plot=True)
print(f"Stored {len(song_fingerprints)} song fingerprints")

# Match clip
result = match_clip(clip_samples, clip_sr, song_fingerprints, 
                    amp_min=best_amp_min, fan_value=best_fan_value, peak_neighborhood_size=best_peak_neighborhood_size,
                    min_match_count=best_min_match_count, min_input_conf=best_min_input_conf, min_db_conf=best_min_db_conf,
                    wsize=best_wsize, wratio=best_wratio, min_hash_time_delta=best_min_hash_time_delta,
                    max_hash_time_delta=best_max_hash_time_delta, fingerprint_reduction=best_fingerprint_reduction,
                    peak_sort=best_peak_sort)
print("\nFinal Matching Result:")
print(result)

# %% [markdown]
# ## Step 5: Integration with RadioPlay
#
# To use the best configuration in your Django system:
# 1. Update settings.py with the best parameters:
#    ```python
#    FINGERPRINT_CONFIG = {
#        'AMP_MIN': <best_amp_min>,
#        'PEAK_NEIGHBORHOOD_SIZE': <best_peak_neighborhood_size>,
#        'FAN_VALUE': <best_fan_value>,
#        'MIN_MATCH_COUNT': <best_min_match_count>,
#        'MIN_INPUT_CONF': <best_min_input_conf>,
#        'MIN_DB_CONF': <best_min_db_conf>,
#        'WINDOW_SIZE': <best_wsize>,
#        'OVERLAP_RATIO': <best_wratio>,
#        'MIN_HASH_TIME_DELTA': <best_min_hash_time_delta>,
#        'MAX_HASH_TIME_DELTA': <best_max_hash_time_delta>,
#        'FINGERPRINT_REDUCTION': <best_fingerprint_reduction>,
#        'PEAK_SORT': <best_peak_sort>
#    }
#    ```
# 2. Save fingerprints to your Fingerprint model:
#    ```python
#    for song_id, h, o in db_fingerprints:
#        Fingerprint.objects.create(song_id=song_id, hash=h, offset=o)
#    ```
# 3. Adapt match_clip to query your database:
#    ```python
#    db_fps = Fingerprint.objects.filter(hash__in=query_hashes)
#    ```
#
# ## Next Steps
#
# - Test with more Ghanaian songs (e.g., Highlife, Hiplife, Afrobeats) and noisy radio clips to validate the configuration.
# - Adjust the number of optuna trials (n_trials) based on computational resources and desired precision.
# - If false positives are a concern, modify the scoring function to penalize low confidence matches.
# - Integrate with your Flutter app for real-time clip processing.
# - If issues persist, check waveform and spectrogram plots, and share logs.
'''

# Split into cells
cells = []
for cell in notebook_script.split("# %%"):
    if cell.strip().startswith("[markdown]"):
        cells.append(nbf.new_markdown_cell(cell.replace("[markdown]", "").strip()))
    else:
        cells.append(nbf.new_code_cell(cell.strip()))

# Create notebook
nb = nbf.new_notebook(cells=cells, metadata={
    "kernelspec": {"name": "python3", "language": "python", "display_name": "Python 3"}
})

# Save to file
with open("Audio_Fingerprinting_Bayesian_Optimization_Demo.ipynb", "w") as f:
    nbformat.write(nb, f)

print("Notebook saved as 'Audio_Fingerprinting_Bayesian_Optimization_Demo.ipynb'")
