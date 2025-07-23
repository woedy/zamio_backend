
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



def simple_match_mp3(clip_samples, clip_sr, song_fingerprints, min_match_threshold=5, plot=False):
    """
    Match a full audio file against stored song fingerprints.
    Suitable for uploaded MP3 or audio clips.
    """
    if not clip_samples.any():
        return {"match": False, "reason": "No samples in clip", "hashes_matched": 0}

    clip_fingerprints = simple_fingerprint(clip_samples, clip_sr, plot=plot)
    if not clip_fingerprints or not song_fingerprints:
        return {"match": False, "reason": "No fingerprints to match", "hashes_matched": 0}

    hash_index = {}
    for song_id, h, o in song_fingerprints:
        hash_index.setdefault(h, []).append((song_id, o))

    match_map = Counter()
    matched_hashes = 0

    for h, q_offset in clip_fingerprints:
        for song_id, db_offset in hash_index.get(h, []):
            delta = db_offset - q_offset
            match_map[(song_id, delta)] += 1
            matched_hashes += 1

    if not match_map:
        return {"match": False, "reason": "No matching hashes", "hashes_matched": 0}

    (song_id, offset), match_count = match_map.most_common(1)[0]
    confidence = (match_count / max(len(clip_fingerprints), 1)) * 100

    if match_count >= min_match_threshold:
        return {
            "match": True,
            "song_id": song_id,
            "offset": offset,
            "hashes_matched": match_count,
            "confidence": round(confidence, 2)
        }
    else:
        return {
            "match": False,
            "reason": "Below match threshold",
            "hashes_matched": match_count,
            "confidence": round(confidence, 2)
        }
    




def simple_match(stream_samples, sr, song_fingerprints, chunk_duration=5, min_match_threshold=10):
    """
    Match against a streaming audio buffer in chunks.
    Suitable for radio streams or long continuous audio.
    """
    chunk_size = int(chunk_duration * sr)
    total_samples = len(stream_samples)

    hash_index = {}
    for song_id, h, o in song_fingerprints:
        hash_index.setdefault(h, []).append((song_id, o))

    matches = []
    i = 0

    while i + chunk_size < total_samples:
        chunk = stream_samples[i:i + chunk_size]
        clip_fingerprints = simple_fingerprint(chunk, sr)

        match_map = Counter()
        for h, q_offset in clip_fingerprints:
            for song_id, db_offset in hash_index.get(h, []):
                delta = db_offset - q_offset
                match_map[(song_id, delta)] += 1

        if match_map:
            (song_id, offset), match_count = match_map.most_common(1)[0]
            confidence = (match_count / max(len(clip_fingerprints), 1)) * 100

            if match_count >= min_match_threshold:
                matches.append({
                    "match": True,
                    "song_id": song_id,
                    "offset": offset,
                    "confidence": round(confidence, 2),
                    "match_count": match_count,
                    "chunk_start": i / sr,
                    "chunk_end": (i + chunk_size) / sr
                })
                i += int(sr * 15)  # skip 15s ahead to avoid overlapping matches
                continue

        i += int(sr * 2)  # slide window by 2s otherwise

    return matches if matches else [{"match": False, "reason": "No valid matches found"}]