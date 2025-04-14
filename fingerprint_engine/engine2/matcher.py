from collections import defaultdict
from fingerprint.models import Fingerprint

def recognize_sample(sample_hashes):
    match_map = defaultdict(list)

    for h, t in sample_hashes:
        matches = Fingerprint.objects.filter(hash=h)
        for match in matches:
            delta = match.offset - t
            match_map[match.song_id].append(delta)

    best_match = None
    highest_count = 0
    for song_id, deltas in match_map.items():
        most_common_offset = max(set(deltas), key=deltas.count)
        count = deltas.count(most_common_offset)
        if count > highest_count:
            best_match = song_id
            highest_count = count

    return best_match, highest_count
