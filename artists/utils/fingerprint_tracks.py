from typing import List, Tuple
from numba import jit
import xxhash
from operator import itemgetter
from collections import Counter
import numpy as np
import librosa
import matplotlib.pyplot as plt
import logging
import os


# Configuration (simplified for the demo)
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

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        # logger.info(f"Detected {len(peaks)} peaks with amp_min={amp_min}") # Removed for simplicity in this demo
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
        # logger.info(f"Generated {valid_pairs} valid peak pairs for hashing") # Removed for simplicity in this demo
        return hashes
    except Exception as e:
        logger.error(f"Hash generation failed: {e}")
        return []
    





def simple_fingerprint(channel_samples, Fs, plot=False): # Added plot parameter
    """Generate fingerprints from audio samples using fixed parameters."""
    try:
        samples = channel_samples.astype(np.float32) / 32768.0
        wsize = CONFIG['DEFAULT_WINDOW_SIZE']
        wratio = CONFIG['DEFAULT_OVERLAP_RATIO']
        hop_length = int(wsize * (1 - wratio))
        S = librosa.stft(samples, n_fft=wsize, hop_length=hop_length, window='hann')
        arr2D = librosa.amplitude_to_db(np.abs(S), ref=np.max)

        amp_min = CONFIG['DEFAULT_AMP_MIN']
        peak_neighborhood_size = CONFIG['PEAK_NEIGHBORHOOD_SIZE']
        peaks = get_2D_peaks(arr2D, plot=plot, amp_min=amp_min, peak_neighborhood_size=peak_neighborhood_size) # Pass plot parameter

        fan_value = CONFIG['DEFAULT_FAN_VALUE']
        min_hash_time_delta = CONFIG['MIN_HASH_TIME_DELTA']
        max_hash_time_delta = CONFIG['MAX_HASH_TIME_DELTA']
        fingerprint_reduction = CONFIG['FINGERPRINT_REDUCTION']
        peak_sort = CONFIG['PEAK_SORT']

        hashes = generate_hashes(peaks, fan_value=fan_value,
                                min_hash_time_delta=min_hash_time_delta,
                                max_hash_time_delta=max_hash_time_delta,
                                fingerprint_reduction=fingerprint_reduction,
                                peak_sort=peak_sort)
        return hashes
    except Exception as e:
        logger.error(f"Simple fingerprinting failed: {e}")
        return []

