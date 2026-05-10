from MCP_Server.arrangement import beats_to_seconds, execute_timed_events, scene_sequence_to_events


def test_beats_to_seconds_uses_tempo():
    assert beats_to_seconds(4, 120) == 2.0


def test_scene_sequence_to_events_accumulates_bars():
    events = scene_sequence_to_events([
        {"scene_index": 0, "bars": 4, "label": "Intro"},
        {"scene_index": 1, "bars": 8, "label": "Verse"},
    ])

    assert events == [
        {"beat": 0.0, "action": "fire_scene", "scene_index": 0, "label": "Intro"},
        {"beat": 16.0, "action": "fire_scene", "scene_index": 1, "label": "Verse"},
    ]


def test_execute_timed_events_dispatches_supported_actions_without_sleeping():
    calls = []

    def send(command, params=None):
        calls.append((command, params))
        return {"ok": True}

    log = execute_timed_events(send, [
        {"beat": 8, "action": "stop_clip", "track_index": 1, "clip_index": 2},
        {"beat": 0, "action": "fire_clip", "track_index": 1, "clip_index": 0},
        {"beat": 4, "action": "set_mixer", "track_index": 1, "volume": 0.5},
    ], tempo=120, realtime=False)

    assert calls == [
        ("fire_clip", {"track_index": 1, "clip_index": 0}),
        ("set_mixer", {"track_index": 1, "volume": 0.5}),
        ("stop_clip", {"track_index": 1, "clip_index": 2}),
    ]
    assert [entry["beat"] for entry in log] == [0.0, 4.0, 8.0]
