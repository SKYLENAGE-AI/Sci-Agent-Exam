from __future__ import annotations

from collections import Counter


def normalize_row(v, row, *, appendix_a=False):
    values = list(row)
    return tuple(sorted(value % v for value in values))


def difference_profile(v, row):
    word = normalize_row(v, row)
    profile = Counter()
    for i, a in enumerate(word):
        for b in word[i + 1 :]:
            diff = (a - b) % v
            profile[min(diff, (-diff) % v)] += 1
    return profile


def codebook_screen(v, k, rows, *, appendix_a=False):
    words = [normalize_row(v, row, appendix_a=appendix_a) for row in rows]
    bound = (v - 1) // (k * (k - 1))
    profiles = [difference_profile(v, word) for word in words]
    repeated_profile_values = sorted(
        value
        for profile in profiles
        for value, count in profile.items()
        if count > 1
    )
    merged = Counter()
    for profile in profiles:
        merged.update(profile)
    coverage_count = sum(merged.values()) * 2
    uncovered_count = max((v - 1) - coverage_count, 0)
    reaches_bound = len(words) >= bound
    return {
        "bound": bound,
        "row_count": len(words),
        "reaches_bound": reaches_bound,
        "repeated_profile_values": repeated_profile_values,
        "uncovered_count": uncovered_count,
    }
