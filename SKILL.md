---
name: ableton-mcp
description: Control Ableton Live through MCP tools, resources, prompts, and producer workflows. Use for session inspection, track/clip editing, device loading, automation, and style recipes.
---

# Ableton MCP

Use this skill when talking to Ableton Live through the AbletonMCP server.

## Operating Rules

1. Read context before edits. Start with `ableton://tracks` or `list_tracks`; use `ableton://session`, `ableton://transport`, and `ableton://scenes` when relevant.
2. Treat indices as volatile. Re-read `list_tracks` after creating, deleting, or duplicating tracks, clips, or scenes.
3. Do not guess browser URIs. Use `get_browser_tree` and `get_browser_items_at_path`, then load the discovered item URI.
4. Prefer additive note edits. `add_notes_to_clip` defaults to `mode="append"`; use `mode="replace"` only when replacing content is intended.
5. Verify visible changes. After loading devices, creating clips, or writing patterns, re-read the track or clip.
6. Confirm destructive edits when the target may matter. `delete_track`, `delete_clip`, `delete_scene`, and `clear_clip_envelope` should be explained before use.
7. Use `ableton://command-log` for recovery when a workflow fails midway.

## MCP Surface

Resources:
- `ableton://session`
- `ableton://tracks`
- `ableton://transport`
- `ableton://scenes`
- `ableton://style-recipes`
- `ableton://command-log`
- `ableton://server-status`

Prompts:
- `build_arrangement(style, scenes)`
- `diagnose_session(goal)`
- `make_clip_variation(track_index, source_clip, destination_clip, intensity)`
- `record_arrangement_plan(style, sections)`

Core tools:
- Read: `get_session_info`, `list_tracks`, `get_track_info`, `get_clip_notes`, `get_transport`, `list_scenes`
- Write: `create_midi_track`, `create_audio_track`, `create_clip`, `add_notes_to_clip`, `set_mixer`, `set_clip_loop`
- Devices: `get_browser_tree`, `get_browser_items_at_path`, `load_browser_item`, `load_device_by_name`, `set_device_parameter`
- Music: `make_pattern`, `variation`, `harmonize`, `style_recipe`, `list_style_recipes`
- Arrangement: `set_arrangement_position`, `set_record_mode`, `start_arrangement_recording`, `stop_arrangement_recording`, `perform_clip_sequence`, `perform_scene_sequence`

## Workflows

For arrangement building, read `references/workflows.md`.
For style mapping and music patterns, read `references/music-recipes.md`.
For safety and recovery rules, read `references/safety.md`.
