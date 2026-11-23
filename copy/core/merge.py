"""Lead/Rhythm baton pass with unison deduplication."""
from __future__ import annotations
import numpy as np

_TICK_PRECISION = 4


def _regions(starts, phrase_gap):
    if len(starts) == 0:
        return []
    starts = np.sort(starts)
    out = []
    rs = float(starts[0])
    re = float(starts[0])
    for s in starts[1:]:
        s = float(s)
        if s - re > phrase_gap:
            out.append((rs, re))
            rs = s
        re = s
    out.append((rs, re))
    return out


def _in_regions(t, regions, slack=0.0):
    for (a, b) in regions:
        if a - slack <= t <= b + slack:
            return True
    return False


def merge_lead_rhythm(lead, rhythm, phrase_gap=1.5, region_slack=0.15):
    if not lead:
        return sorted(rhythm, key=lambda x: (x[0], x[2]))
    if not rhythm:
        return sorted(lead, key=lambda x: (x[0], x[2]))

    lead_starts = np.array([n[0] for n in lead], dtype=float)
    regions = _regions(lead_starts, phrase_gap)
    lead_ticks = {round(t, _TICK_PRECISION) for (t, _, _) in lead}

    merged = list(lead)
    for rn in rhythm:
        if _in_regions(rn[0], regions, slack=region_slack):
            continue
        if round(rn[0], _TICK_PRECISION) in lead_ticks:
            continue
        merged.append(rn)

    merged.sort(key=lambda x: (x[0], x[2]))
    return merged