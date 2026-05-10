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
