import json

import MCP_Server.server as server


def test_style_recipes_resource_uses_shared_recipe_catalog():
    payload = json.loads(server.style_recipes_resource())

    assert "deep-house" in payload
    assert payload["trap"].startswith("Modern trap")


def test_command_log_resource_reports_destructive_commands():
    server.COMMAND_LOG.clear()

    server._log_command("delete_clip", {"track_index": 1, "clip_index": 2}, "success")
    payload = json.loads(server.command_log_resource())

    assert payload["commands"][0]["command"] == "delete_clip"
    assert payload["commands"][0]["destructive"] is True


def test_server_status_resource_documents_transport_and_safety():
    payload = json.loads(server.server_status_resource())

    assert payload["transport"] == "tcp-ndjson"
    assert payload["host"] == server.DEFAULT_HOST
    assert "delete_track" in payload["destructive_commands"]


def test_prompts_embed_workflow_instructions():
    prompt = server.build_arrangement(style="trap", scenes=4)

    assert "ableton://tracks" in prompt
    assert "verify with list_tracks" in prompt
    assert "trap" in prompt


def test_parse_arrangement_dsl_returns_compact_preview(monkeypatch):
    def fake_send(command, params=None):
        if command == "get_session_info":
            return {"scene_count": 8}
        if command == "get_transport":
            return {"tempo": 140.0}
        raise AssertionError(command)

    monkeypatch.setattr(server, "_send", fake_send)
    payload = json.loads(server.parse_arrangement_dsl(
        None,
        "style=ukg; bpm=138; template=club44; scenes=A,B,C,D",
        verbosity="compact",
    ))

    assert payload["preview"]["total_bars"] == 44.0
    assert payload["preview"]["sections"] == 8


def test_plan_slot_save_load_patch(monkeypatch):
    state = {}

    monkeypatch.setattr(server, "_memory_load", lambda: dict(state))
    monkeypatch.setattr(server, "_memory_save", lambda data: state.update(data))
    monkeypatch.setattr(server, "_send", lambda command, params=None: {"tempo": 120.0} if command == "get_transport" else {"scene_count": 8})

    spec = {"sections": [{"scene_index": 0, "bars": 4}, {"scene_index": 1, "bars": 4}]}
    saved = json.loads(server.save_arrangement_plan(None, "current", spec))
    loaded = json.loads(server.load_arrangement_plan(None, "current", verbosity="compact"))
    patched = json.loads(server.patch_arrangement_plan(None, "current", "section[1].bars=8", verbosity="compact"))

    assert saved["saved"] is True
    assert loaded["plan"]["sections"] == 2
    assert patched["plan"]["total_bars"] == 12.0


def test_compose_arrangement_preview_mode(monkeypatch):
    commands = []

    def fake_send(command, params=None):
        commands.append(command)
        if command == "get_session_info":
            return {"scene_count": 8}
        if command == "get_transport":
            return {"tempo": 140.0}
        raise AssertionError(command)

    state = {}
    monkeypatch.setattr(server, "_send", fake_send)
    monkeypatch.setattr(server, "_memory_load", lambda: dict(state))
    monkeypatch.setattr(server, "_memory_save", lambda data: state.update(data))

    payload = json.loads(server.compose_arrangement(
        None,
        goal_prompt="make me a 32 bars trap arrangement at 150 bpm",
        mode="preview",
        verbosity="compact",
    ))

    assert payload["mode"] == "preview"
    assert payload["plan"]["total_bars"] == 32.0
    assert "get_transport" in commands
