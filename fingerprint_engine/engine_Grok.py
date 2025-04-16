import numpy as np
import librosa
from numba import jit
import xxhash
from scipy.ndimage import maximum_filter
from scipy.ndimage.morphology import generate_binary_structure, binary_erosion, iterate_structure
from typing import List, Tuple
import logging
from operator import itemgetter
import settings  # Assuming your settings module exists

logger = logging.getLogger(__name__)

def fingerprint(channel_samples: List[int], Fs: int = settings.DEFAULT_FS, 
                wsize: int = settings.DEFAULT_WINDOW_SIZE, wratio: float = settings.DEFAULT_OVERLAP_RATIO,
                fan_value: int = settings.DEFAULT_FAN_VALUE, amp_min: int = settings.DEFAULT_AMP_MIN,
                chunk_size: int = None) -> List[Tuple[str, int]]:
    """
    Generate fingerprints from audio samples using librosa and numba for optimization.
    
    Args:
        channel_samples: Raw audio samples (int16).
        Fs: Sampling rate (Hz).
        wsize: FFT window size.
        wratio: Overlap ratio for spectrogram.
        fan_value: Number of peaks to combine per hash.
        amp_min: Minimum amplitude for peak detection.
        chunk_size: Size of audio chunks for parallel processing (None for single chunk).
    
    Returns:
        List of (hash, offset) tuples representing fingerprints.
    """
    try:
        # Convert samples to float32 for librosa
        samples = np.array(channel_samples, dtype=np.float32) / 32768.0  # Normalize int16 to [-1, 1]

        # Compute spectrogram with librosa (replaces mlab.specgram)
        hop_length = int(wsize * (1 - wratio))
        S = librosa.stft(samples, n_fft=wsize, hop_length=hop_length, window='hann')
        arr2D = librosa.amplitude_to_db(np.abs(S), ref=np.max)  # Log-scale spectrogram

        # Get peaks using optimized numba function
        local_maxima = get_2D_peaks(arr2D, amp_min=amp_min)

        # Generate hashes
        hashes = generate_hashes(local_maxima, fan_value=fan_value)

        logger.info(f"Generated {len(hashes)} fingerprints for {len(samples)/Fs:.2f}s audio")
        return hashes

    except Exception as e:
        logger.error(f"Fingerprinting failed: {e}")
        return []

@jit(nopython=True)
def get_2D_peaks_numba(arr2D: np.ndarray, amp_min: float) -> List[Tuple[int, int]]:
    """
    Optimized peak detection using numba for speed.
    
    Args:
        arr2D: Spectrogram matrix (frequency x time).
        amp_min: Minimum amplitude threshold.
    
    Returns:
        List of (frequency, time) tuples for detected peaks.
    """
    peaks = []
    rows, cols = arr2D.shape

    # Define neighborhood size for local maxima (same as original)
    neighborhood_size = settings.PEAK_NEIGHBORHOOD_SIZE // 2

    for i in range(neighborhood_size, rows - neighborhood_size):
        for j in range(neighborhood_size, cols - neighborhood_size):
            # Check if current point is a local maximum
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

def get_2D_peaks(arr2D: np.ndarray, plot: bool = False, 
                 amp_min: float = settings.DEFAULT_AMP_MIN) -> List[Tuple[int, int]]:
    """
    Extract peaks from spectrogram using numba for performance.
    
    Args:
        arr2D: Spectrogram matrix.
        plot: If True, visualize peaks (for debugging).
        amp_min: Minimum amplitude threshold.
    
    Returns:
        List of (frequency, time) tuples for peaks.
    """
    try:
        # Use numba-optimized peak detection
        peaks = get_2D_peaks_numba(arr2D, amp_min)

        if plot:
            import matplotlib.pyplot as plt
            plt.imshow(arr2D, origin='lower')
            if peaks:
                freqs, times = zip(*peaks)
                plt.scatter(times, freqs, c='r', s=10)
            plt.gca().invert_yaxis()
            plt.title("Spectrogram with Detected Peaks")
            plt.xlabel("Time")
            plt.ylabel("Frequency")
            plt.show()

        return peaks

    except Exception as e:
        logger.error(f"Peak detection failed: {e}")
        return []

def generate_hashes(peaks: List[Tuple[int, int]], 
                    fan_value: int = settings.DEFAULT_FAN_VALUE) -> List[Tuple[str, int]]:
    """
    Generate hashes from peaks using xxhash for speed.
    
    Args:
        peaks: List of (frequency, time) tuples.
        fan_value: Number of peaks to combine per hash.
    
    Returns:
        List of (hash, offset) tuples.
    """
    try:
        idx_freq = 0
        idx_time = 1
        if settings.PEAK_SORT:
            peaks.sort(key=itemgetter(idx_time))

        hashes = []
        for i in range(len(peaks)):
            for j in range(1, fan_value):
                if (i + j) < len(peaks):
                    freq1 = peaks[i][idx_freq]
                    freq2 = peaks[i + j][idx_freq]
                    t1 = peaks[i][idx_time]
                    t2 = peaks[i + j][idx_time]
                    t_delta = t2 - t1

                    if settings.MIN_HASH_TIME_DELTA <= t_delta <= settings.MAX_HASH_TIME_DELTA:
                        # Use xxhash instead of SHA1
                        h = xxhash.xxh64(f"{freq1}|{freq2}|{t_delta}".encode('utf-8'))
                        hash_str = h.hexdigest()[:settings.FINGERPRINT_REDUCTION]
                        hashes.append((hash_str, t1))

        return hashes

    except Exception as e:
        logger.error(f"Hash generation failed: {e}")
        return []