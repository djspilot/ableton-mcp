import pytest

from MCP_Server.arrangement import (
    apply_spec_patch,
    arrangement_presets,
    beats_to_seconds,
    compact_plan,
    compile_scene_arrangement_spec,
    execute_timed_events,
    parse_patch_text,
    scene_sequence_to_events,
    spec_from_dsl,
)


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


def test_compile_scene_arrangement_spec_builds_deterministic_timeline():
    plan = compile_scene_arrangement_spec({
        "start_beat": 8,
        "sections": [
            {"scene_index": 0, "bars": 4, "label": "Intro"},
            {"scene_index": 1, "duration_beats": 32},
        ],
        "record": True,
        "realtime": False,
    }, default_tempo=120)

    assert plan["tempo"] == 120.0
    assert plan["total_beats"] == 48.0
    assert plan["end_beat"] == 56.0
    assert plan["events"] == [
        {"beat": 8.0, "action": "fire_scene", "scene_index": 0, "label": "Intro"},
        {"beat": 24.0, "action": "fire_scene", "scene_index": 1, "label": "Scene 1"},
    ]
    assert plan["timeline"][1]["duration_bars"] == 8.0


def test_compile_scene_arrangement_spec_requires_scene_index():
    with pytest.raises(ValueError, match="scene_index"):
        compile_scene_arrangement_spec({"sections": [{"bars": 4}]})


def test_spec_from_dsl_uses_template_and_scene_tokens():
    spec = spec_from_dsl(
        "style=ukg; bpm=138; template=club44; scenes=A,C; record=false; realtime=false; kit=909a",
        default_tempo=120,
        scene_count=8,
    )
    assert spec["tempo"] == 138.0
    assert spec["record"] is False
    assert spec["realtime"] is False
    assert len(spec["sections"]) == 8
    assert spec["sections"][0]["scene_index"] == 0
    assert spec["sections"][1]["scene_index"] == 2
    assert spec["preset_ids"]["kit"] == "909a"


def test_apply_spec_patch_supports_set_and_swap():
    spec = {
        "sections": [
            {"scene_index": 0, "bars": 4},
            {"scene_index": 1, "bars": 8},
        ]
    }
    updated = apply_spec_patch(spec, {"op": "set", "path": "section[1].bars", "value": 16})
    swapped = apply_spec_patch(updated, {"op": "swap_scene", "old_scene": 0, "new_scene": 3})
    assert swapped["sections"][0]["scene_index"] == 3
    assert swapped["sections"][1]["bars"] == 16


def test_parse_patch_text_supports_short_commands():
    set_patch = parse_patch_text("section[2].bars=8")
    swap_patch = parse_patch_text("swap scene A->C", scene_count=8)
    assert set_patch == {"op": "set", "path": "section[2].bars", "value": 8}
    assert swap_patch["op"] == "swap_scene"
    assert swap_patch["old_scene"] == 0
    assert swap_patch["new_scene"] == 2


def test_compact_plan_and_presets_are_available():
    plan = compile_scene_arrangement_spec({
        "sections": [{"scene_index": 0, "bars": 4}],
    }, default_tempo=120)
    compact = compact_plan(plan)
    assert compact["sections"] == 1
    assert "club44" in arrangement_presets()["templates"]
