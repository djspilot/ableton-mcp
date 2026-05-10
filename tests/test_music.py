from MCP_Server.music import harmonize_notes, make_notes, root_pitch, vary_notes


def test_make_notes_is_deterministic_with_seed():
    first = make_notes("donk", bars=2, key="F", humanize_notes=True, seed=42)
    second = make_notes("donk", bars=2, key="F", humanize_notes=True, seed=42)

    assert first == second
    assert all(0 <= note["pitch"] <= 127 for note in first)
    assert all(note["start_time"] >= 0 for note in first)


def test_make_notes_supports_melodic_scale_context():
    notes = make_notes("arp", bars=1, key="D", scale="minor", octave=4, humanize_notes=False)

    assert notes[0]["pitch"] == root_pitch("D", 4)
    assert len(notes) == 16
    assert notes[-1]["start_time"] == 3.75


def test_vary_notes_preserves_input_notes():
    source = [{"pitch": 60, "start_time": 0.0, "duration": 1.0, "velocity": 90}]

    varied = vary_notes(source, intensity=0.7, seed=3)

    assert source == [{"pitch": 60, "start_time": 0.0, "duration": 1.0, "velocity": 90}]
    assert varied
    assert all(0 <= note["pitch"] <= 127 for note in varied)


def test_harmonize_notes_maps_to_requested_interval():
    source = [{"pitch": 60, "start_time": 0.0, "duration": 1.0, "velocity": 100}]

    harmony = harmonize_notes(source, key="C", scale="major", interval="third")

    assert harmony == [{"pitch": 64, "start_time": 0.0, "duration": 1.0, "velocity": 85}]
