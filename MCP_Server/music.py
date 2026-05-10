import random
from typing import Any, Dict, List, Optional


SCALES = {
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "major": [0, 2, 4, 5, 7, 9, 11],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "minor_pentatonic": [0, 3, 5, 7, 10],
    "major_pentatonic": [0, 2, 4, 7, 9],
    "blues": [0, 3, 5, 6, 7, 10],
}

NOTE_NAMES = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4,
    "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9,
    "A#": 10, "Bb": 10, "B": 11,
}


def root_pitch(key: str, octave: int = 3) -> int:
    return 12 * (octave + 1) + NOTE_NAMES.get(key.strip().capitalize(), 0)


def scale_pitches(key: str, scale: str, octave: int, count: int) -> List[int]:
    intervals = SCALES.get(scale, SCALES["minor"])
    root = root_pitch(key, octave)
    return [root + intervals[i % len(intervals)] + 12 * (i // len(intervals)) for i in range(count)]


def humanize(notes: List[Dict[str, Any]], timing_jitter: float = 0.01,
             vel_jitter: int = 8, seed: Optional[int] = None) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    out = []
    for note in notes:
        next_note = dict(note)
        next_note["start_time"] = max(0.0, next_note["start_time"] + rng.uniform(-timing_jitter, timing_jitter))
        next_note["velocity"] = max(1, min(127, int(next_note["velocity"] + rng.randint(-vel_jitter, vel_jitter))))
        out.append(next_note)
    return out


def pattern_four_on_floor(bars: int, key: str = "C") -> List[Dict[str, Any]]:
    notes = []
    for beat in range(bars * 4):
        notes.append({"pitch": 36, "start_time": beat * 1.0, "duration": 0.25, "velocity": 110})
        if beat % 4 in (1, 3):
            notes.append({"pitch": 38, "start_time": beat * 1.0, "duration": 0.25, "velocity": 100})
        notes.append({"pitch": 42, "start_time": beat * 1.0, "duration": 0.125, "velocity": 80})
        notes.append({"pitch": 42, "start_time": beat * 1.0 + 0.5, "duration": 0.125, "velocity": 70})
        if beat % 4 == 3:
            notes.append({"pitch": 46, "start_time": beat * 1.0 + 0.5, "duration": 0.25, "velocity": 90})
    return notes


def pattern_breakbeat(bars: int, key: str = "C") -> List[Dict[str, Any]]:
    notes = []
    for bar in range(bars):
        base = bar * 4.0
        for time in [0.0, 2.5, 3.75]:
            notes.append({"pitch": 36, "start_time": base + time, "duration": 0.25, "velocity": 115})
        for time in [1.0, 3.0]:
            notes.append({"pitch": 38, "start_time": base + time, "duration": 0.25, "velocity": 105})
        for time in [1.75, 2.25]:
            notes.append({"pitch": 38, "start_time": base + time, "duration": 0.125, "velocity": 45})
        for i in range(8):
            notes.append({"pitch": 42, "start_time": base + i * 0.5, "duration": 0.125,
                          "velocity": 70 + (15 if i % 2 == 0 else 0)})
    return notes


def pattern_trap_hats(bars: int, key: str = "C", seed: Optional[int] = None) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    notes = []
    for bar in range(bars):
        base = bar * 4.0
        for time in [0.0, 1.0, 2.0, 3.0]:
            notes.append({"pitch": 36, "start_time": base + time, "duration": 0.25, "velocity": 110})
        for time in [1.0, 3.0]:
            notes.append({"pitch": 38, "start_time": base + time, "duration": 0.25, "velocity": 100})
        time = 0.0
        while time < 4.0:
            if rng.random() < 0.18:
                for k in range(2):
                    notes.append({"pitch": 42, "start_time": base + time + k * 0.125,
                                  "duration": 0.0625, "velocity": 70 + rng.randint(-10, 20)})
                time += 0.25
            else:
                notes.append({"pitch": 42, "start_time": base + time, "duration": 0.0625,
                              "velocity": 75 + rng.randint(-10, 15)})
                time += 0.25
    return notes


def pattern_reese_bassline(bars: int, key: str = "C") -> List[Dict[str, Any]]:
    root = root_pitch(key, 1)
    notes = []
    for bar in range(bars):
        base = bar * 4.0
        notes.append({"pitch": root, "start_time": base, "duration": 2.5, "velocity": 110})
        notes.append({"pitch": root, "start_time": base + 2.75, "duration": 0.25, "velocity": 100})
        notes.append({"pitch": root + 7, "start_time": base + 3.25, "duration": 0.5, "velocity": 95})
    return notes


def pattern_arp(bars: int, key: str = "C", scale: str = "minor", octave: int = 4,
                step: float = 0.25, length: int = 8) -> List[Dict[str, Any]]:
    pitches = scale_pitches(key, scale, octave, length)
    return [{"pitch": pitches[i % len(pitches)], "start_time": i * step,
             "duration": step * 0.9, "velocity": 90}
            for i in range(int((bars * 4.0) / step))]


def pattern_chord_stab(bars: int, key: str = "C", scale: str = "minor",
                       octave: int = 4) -> List[Dict[str, Any]]:
    intervals = SCALES.get(scale, SCALES["minor"])
    root = root_pitch(key, octave)
    chord = [root, root + intervals[2], root + intervals[4]]
    notes = []
    for bar in range(bars):
        base = bar * 4.0
        for time in [0.0, 1.5, 2.0, 3.5]:
            for pitch in chord:
                notes.append({"pitch": pitch, "start_time": base + time, "duration": 0.25, "velocity": 90})
    return notes


def pattern_donk(bars: int, key: str = "C", seed: Optional[int] = None) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    root = root_pitch(key, 3)
    notes = []
    for bar in range(bars):
        base = bar * 4.0
        for time in [0.5, 1.5, 2.5, 3.5]:
            pitch = root if rng.random() < 0.75 else root + 7
            notes.append({"pitch": pitch, "start_time": base + time,
                          "duration": 0.18, "velocity": 110 + rng.randint(-8, 8)})
        if rng.random() < 0.4:
            notes.append({"pitch": root, "start_time": base + 3.75,
                          "duration": 0.1, "velocity": 80})
    return notes


def pattern_ukg_shuffle(bars: int, key: str = "C") -> List[Dict[str, Any]]:
    notes = []
    swing = 0.083
    for bar in range(bars):
        base = bar * 4.0
        notes.append({"pitch": 36, "start_time": base + 0.0, "duration": 0.25, "velocity": 115})
        notes.append({"pitch": 36, "start_time": base + 1.75, "duration": 0.25, "velocity": 105})
        notes.append({"pitch": 38, "start_time": base + 2.0, "duration": 0.25, "velocity": 110})
        notes.append({"pitch": 38, "start_time": base + 3.5, "duration": 0.125, "velocity": 60})
        for i in range(8):
            time = base + i * 0.5
            notes.append({"pitch": 42, "start_time": time, "duration": 0.125,
                          "velocity": 90 if i % 2 == 0 else 65})
            notes.append({"pitch": 42, "start_time": time + 0.25 + swing, "duration": 0.1,
                          "velocity": 55})
    return notes


def pattern_bassline_house(bars: int, key: str = "C") -> List[Dict[str, Any]]:
    intervals = SCALES["minor"]
    root = root_pitch(key, 2)
    melody_intervals = [0, 0, intervals[2], 0, intervals[4], 0, intervals[2], intervals[4]]
    notes = []
    for bar in range(bars):
        base = bar * 4.0
        for i in range(8):
            interval = melody_intervals[(i + bar) % len(melody_intervals)]
            notes.append({"pitch": root + interval, "start_time": base + i * 0.5,
                          "duration": 0.42, "velocity": 105})
    return notes


def pattern_garage_bass(bars: int, key: str = "C") -> List[Dict[str, Any]]:
    root = root_pitch(key, 2)
    notes = []
    for bar in range(bars):
        base = bar * 4.0
        notes.append({"pitch": root, "start_time": base, "duration": 1.4, "velocity": 110})
        notes.append({"pitch": root + 12, "start_time": base + 1.5, "duration": 0.25, "velocity": 95})
        notes.append({"pitch": root, "start_time": base + 2.0, "duration": 1.4, "velocity": 110})
        notes.append({"pitch": root + 12, "start_time": base + 3.5, "duration": 0.25, "velocity": 95})
    return notes


PATTERNS = {
    "four-on-floor": pattern_four_on_floor,
    "four_on_floor": pattern_four_on_floor,
    "breakbeat": pattern_breakbeat,
    "amen": pattern_breakbeat,
    "trap": pattern_trap_hats,
    "trap-hats": pattern_trap_hats,
    "reese": pattern_reese_bassline,
    "reese-bassline": pattern_reese_bassline,
    "arp": pattern_arp,
    "chord-stab": pattern_chord_stab,
    "chords": pattern_chord_stab,
    "donk": pattern_donk,
    "ukg-shuffle": pattern_ukg_shuffle,
    "garage": pattern_ukg_shuffle,
    "bassline-house": pattern_bassline_house,
    "bassline": pattern_bassline_house,
    "garage-bass": pattern_garage_bass,
    "speed-garage": pattern_garage_bass,
}


def make_notes(style: str, bars: int = 1, key: str = "C", scale: str = "minor",
               octave: int = 4, humanize_notes: bool = True,
               seed: Optional[int] = None) -> List[Dict[str, Any]]:
    fn = PATTERNS.get(style.lower())
    if not fn:
        raise ValueError("Unknown style '%s'. Choices: %s" % (style, ", ".join(sorted(PATTERNS.keys()))))
    if fn in (pattern_arp, pattern_chord_stab):
        notes = fn(bars, key=key, scale=scale, octave=octave)
    elif fn in (pattern_trap_hats, pattern_donk):
        notes = fn(bars, key=key, seed=seed)
    else:
        notes = fn(bars, key=key)
    return humanize(notes, seed=seed) if humanize_notes else notes


def vary_notes(notes: List[Dict[str, Any]], intensity: float = 0.5,
               seed: Optional[int] = None) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    out = []
    for note in notes:
        if rng.random() < 0.15 * intensity:
            continue
        next_note = dict(note)
        if rng.random() < 0.25 * intensity:
            next_note["pitch"] = max(0, min(127, next_note["pitch"] + rng.choice([-12, 12])))
        if rng.random() < 0.30 * intensity:
            next_note["velocity"] = max(20, min(120, int(next_note["velocity"] * rng.uniform(0.5, 1.1))))
        out.append(next_note)
        if rng.random() < 0.20 * intensity:
            ghost = dict(next_note)
            ghost["start_time"] = next_note["start_time"] + next_note["duration"] * 0.5
            ghost["velocity"] = max(20, next_note["velocity"] // 3)
            out.append(ghost)
    return out


def harmonize_notes(notes: List[Dict[str, Any]], key: str = "C", scale: str = "minor",
                    interval: str = "third") -> List[Dict[str, Any]]:
    intervals = SCALES.get(scale, SCALES["minor"])
    root = root_pitch(key, 0) % 12
    step_map = {"third": 2, "fifth": 4, "sixth": 5, "octave_down": -7, "octave_up": 7}
    step = step_map.get(interval, 2)

    def snap(pitch: int, step_offset: int) -> int:
        rel = (pitch - root) % 12
        octv = (pitch - root) // 12
        degree = min(range(len(intervals)), key=lambda i: abs(intervals[i] - rel))
        new_degree = degree + step_offset
        octave_shift = new_degree // len(intervals)
        new_degree %= len(intervals)
        return root + 12 * (octv + octave_shift) + intervals[new_degree]

    out = []
    for note in notes:
        next_note = dict(note)
        next_note["pitch"] = max(0, min(127, snap(next_note["pitch"], step)))
        next_note["velocity"] = max(20, int(next_note["velocity"] * 0.85))
        out.append(next_note)
    return out
