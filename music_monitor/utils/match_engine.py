
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

from artists.utils.fingerprint_tracks import simple_fingerprint


def simple_match(clip_samples, clip_sr, song_fingerprints, plot=False): # Added clip_samples, clip_sr, and plot parameters
    """Basic matching of clip fingerprints against song fingerprints."""
    if len(clip_samples) == 0:
        return {"match": False, "reason": "No samples in clip", "hashes_matched": 0}

    # Visualize clip waveform
    if plot: # Added plot condition
        plt.figure(figsize=(10, 4))
        plt.plot(clip_samples)
        plt.title('Clip Waveform')
        plt.xlabel('Sample')
        plt.ylabel('Amplitude')
        plt.show()

    # Generate clip fingerprints
    clip_fingerprints = simple_fingerprint(clip_samples, clip_sr, plot=plot) # Pass plot parameter to simple_fingerprint

    if not clip_fingerprints or not song_fingerprints:
        return {"match": False, "reason": "No fingerprints to match", "hashes_matched": 0}

    # Create dictionaries for faster lookup
    song_hash_dict = {}
    for song_id, h, o in song_fingerprints:
        if h not in song_hash_dict:
            song_hash_dict[h] = []
        song_hash_dict[h].append((song_id, o))

    match_map = Counter()
    matched_hashes_count = 0
    for h, query_offset in clip_fingerprints:
        if h in song_hash_dict:
            for song_id, db_offset in song_hash_dict[h]:
                offset_diff = db_offset - query_offset
                match_map[(song_id, offset_diff)] += 1
                matched_hashes_count += 1 # Count each individual match

    if not match_map:
        return {"match": False, "reason": "No matching hashes found", "hashes_matched": 0}

    (song_id, offset_diff), match_count = match_map.most_common(1)[0]

    # Simple threshold for match
    min_simple_match_threshold = 5 # Define a simple threshold

    if match_count >= min_simple_match_threshold:
        return {
            "match": True,
            "song_id": song_id,
            "offset": offset_diff,
            "hashes_matched": match_count
        }
    else:
        return {
            "match": False,
            "reason": "Below simple match threshold",
            "hashes_matched": match_count
        }
