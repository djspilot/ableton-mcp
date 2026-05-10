from typing import Any, Dict


STYLE_RECIPES: Dict[str, Dict[str, Any]] = {
    "uk-bassline": {
        "description": "Northern UK bassline / donk rap. 138 BPM, F minor, 5x5 grid.",
        "tempo": 138,
        "time_sig": [4, 4],
        "key": "F",
        "scale": "minor",
        "tracks": [
            {"name": "DRUMS", "kind": "midi", "load": [{"category": "drums", "name": "Drum Rack"}]},
            {"name": "SUB", "kind": "midi", "load": [{"category": "instruments", "name": "Wavetable"}]},
            {"name": "DONK", "kind": "midi",
             "load": [{"category": "instruments", "name": "Operator"},
                      {"category": "audio_effects", "name": "Saturator"}]},
            {"name": "REESE", "kind": "midi",
             "load": [{"category": "instruments", "name": "Wavetable"},
                      {"category": "audio_effects", "name": "Auto Filter"},
                      {"category": "audio_effects", "name": "Saturator"}]},
            {"name": "STAB", "kind": "midi",
             "load": [{"category": "instruments", "name": "Wavetable"},
                      {"category": "audio_effects", "name": "Hybrid Reverb"}]},
        ],
        "scenes": [
            {"name": "Intro", "patterns": {"DRUMS": ("ukg-shuffle", 2), "REESE": ("reese", 2)}},
            {"name": "Build", "patterns": {"DRUMS": ("four-on-floor", 2), "SUB": ("garage-bass", 2),
                                            "DONK": ("donk", 2)}},
            {"name": "Drop", "patterns": {"DRUMS": ("four-on-floor", 2), "SUB": ("bassline-house", 2),
                                           "DONK": ("donk", 2), "REESE": ("reese", 2),
                                           "STAB": ("chord-stab", 2)}},
            {"name": "Breakdown", "patterns": {"REESE": ("reese", 4), "STAB": ("chord-stab", 4)}},
            {"name": "Outro", "patterns": {"DRUMS": ("four-on-floor", 2), "SUB": ("garage-bass", 2),
                                            "STAB": ("chord-stab", 2)}},
        ],
        "mixer_hints": {
            "DRUMS": {"volume": 0.85},
            "SUB": {"volume": 0.80},
            "DONK": {"volume": 0.70, "panning": 0.15},
            "REESE": {"volume": 0.65, "panning": -0.15},
            "STAB": {"volume": 0.55},
        },
    },
    "trap": {
        "description": "Modern trap: 808s, fast hats, half-time snares. 140 BPM, A minor.",
        "tempo": 140,
        "time_sig": [4, 4],
        "key": "A",
        "scale": "minor",
        "tracks": [
            {"name": "DRUMS", "kind": "midi", "load": [{"category": "drums", "name": "Drum Rack"}]},
            {"name": "808", "kind": "midi", "load": [{"category": "instruments", "name": "Operator"}]},
            {"name": "LEAD", "kind": "midi", "load": [{"category": "instruments", "name": "Wavetable"}]},
        ],
        "scenes": [
            {"name": "Intro", "patterns": {"DRUMS": ("trap", 2)}},
            {"name": "Verse", "patterns": {"DRUMS": ("trap", 2), "808": ("reese", 2)}},
            {"name": "Hook", "patterns": {"DRUMS": ("trap", 2), "808": ("reese", 2), "LEAD": ("arp", 2)}},
        ],
        "mixer_hints": {"DRUMS": {"volume": 0.85}, "808": {"volume": 0.85}, "LEAD": {"volume": 0.7}},
    },
    "deep-house": {
        "description": "Classic deep house: warm 4x4 kick, off-beat hats, rolling sub bass. 124 BPM, C minor.",
        "tempo": 124,
        "time_sig": [4, 4],
        "key": "C",
        "scale": "minor",
        "tracks": [
            {"name": "DRUMS", "kind": "midi", "load": [{"category": "drums", "name": "Drum Rack"}]},
            {"name": "BASS", "kind": "midi", "load": [{"category": "instruments", "name": "Wavetable"}]},
            {"name": "CHORD", "kind": "midi",
             "load": [{"category": "instruments", "name": "Wavetable"},
                      {"category": "audio_effects", "name": "Hybrid Reverb"}]},
        ],
        "scenes": [
            {"name": "Intro", "patterns": {"DRUMS": ("four-on-floor", 4)}},
            {"name": "Groove", "patterns": {"DRUMS": ("four-on-floor", 4), "BASS": ("garage-bass", 4)}},
            {"name": "Peak", "patterns": {"DRUMS": ("four-on-floor", 4), "BASS": ("garage-bass", 4),
                                           "CHORD": ("chord-stab", 4)}},
        ],
        "mixer_hints": {"DRUMS": {"volume": 0.85}, "BASS": {"volume": 0.80}, "CHORD": {"volume": 0.65}},
    },
}


def recipe_summary() -> Dict[str, str]:
    return {key: value["description"] for key, value in STYLE_RECIPES.items()}
