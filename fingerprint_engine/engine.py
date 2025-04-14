import hashlib
from operator import itemgetter
from typing import List, Tuple
import numpy as np
from scipy.ndimage.filters import maximum_filter
from scipy.ndimage.morphology import generate_binary_structure, iterate_structure, binary_erosion
import matplotlib.mlab as mlab
from django.conf import settings

def fingerprint(channel_samples: List[int], Fs: int = settings.DEFAULT_FS, wsize: int = settings.DEFAULT_WINDOW_SIZE,
                wratio: float = settings.DEFAULT_OVERLAP_RATIO, fan_value: int = settings.DEFAULT_FAN_VALUE,
                amp_min: int = settings.DEFAULT_AMP_MIN) -> List[Tuple[str, int]]:
    """
    Generate fingerprints from audio samples.
    """
    # Compute the spectrogram
    arr2D = mlab.specgram(channel_samples, NFFT=wsize, Fs=Fs, window=mlab.window_hanning,
                          noverlap=int(wsize * wratio))[0]

    # Apply log transform
    arr2D = 10 * np.log10(arr2D, out=np.zeros_like(arr2D), where=(arr2D != 0))

    # Get 2D peaks from the spectrogram
    local_maxima = get_2D_peaks(arr2D, amp_min=amp_min)

    # Generate and return hashes
    return generate_hashes(local_maxima, fan_value=fan_value)

def get_2D_peaks(arr2D: np.array, plot: bool = False, amp_min: int = settings.DEFAULT_AMP_MIN) -> List[Tuple[int, int]]:
    """
    Extract maximum peaks from the spectrogram matrix (arr2D).
    """
    # Create binary structure for neighborhood filter
    struct = generate_binary_structure(2, settings.CONNECTIVITY_MASK)
    neighborhood = iterate_structure(struct, settings.PEAK_NEIGHBORHOOD_SIZE)

    # Find local maxima
    local_max = maximum_filter(arr2D, footprint=neighborhood) == arr2D

    # Apply erosion to remove noise
    background = (arr2D == 0)
    eroded_background = binary_erosion(background, structure=neighborhood, border_value=1)

    # Boolean mask of true peaks
    detected_peaks = local_max != eroded_background

    # Extract frequencies and times of detected peaks
    amps = arr2D[detected_peaks]
    freqs, times = np.where(detected_peaks)

    # Filter peaks by minimum amplitude
    filter_idxs = np.where(amps > amp_min)
    freqs_filter = freqs[filter_idxs]
    times_filter = times[filter_idxs]

    if plot:
        import matplotlib.pyplot as plt
        plt.imshow(arr2D)
        plt.scatter(times_filter, freqs_filter)
        plt.gca().invert_yaxis()
        plt.show()

    return list(zip(freqs_filter, times_filter))

def generate_hashes(peaks: List[Tuple[int, int]], fan_value: int = settings.DEFAULT_FAN_VALUE) -> List[Tuple[str, int]]:
    """
    Generate hashes from the given peaks and time differences.
    """
    idx_freq = 0
    idx_time = 1
    if settings.PEAK_SORT:
        peaks.sort(key=itemgetter(1))

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
                    # Generate SHA1 hash
                    h = hashlib.sha1(f"{str(freq1)}|{str(freq2)}|{str(t_delta)}".encode('utf-8'))
                    hashes.append((h.hexdigest()[:settings.FINGERPRINT_REDUCTION], t1))

    return hashes
