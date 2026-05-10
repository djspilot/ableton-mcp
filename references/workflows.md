# Ableton MCP Workflows

## Build An Arrangement

1. Read `ableton://tracks` and `ableton://style-recipes`.
2. Select a style recipe with `style_recipe(style)`.
3. Create only missing tracks and scenes.
4. After each structural change, call `list_tracks`.
5. Load devices by discovery:
   - `get_browser_tree(category_type="instruments", max_depth=2)`
   - `get_browser_items_at_path("instruments/Wavetable")`
   - `load_browser_item(track_index, item_uri)`
6. Write one clip at a time with `make_pattern`.
7. Verify clip contents with `get_clip_notes` or track structure with `get_track_info`.

## Record An Arrangement Performance

1. Read `ableton://tracks`, `ableton://scenes`, and `ableton://transport`.
2. Build a beat-timed plan using track names or scene indices.
3. Prefer scene sequences when the grid is already coherent:
   - `perform_scene_sequence(sequence=[{"scene_index": 0, "bars": 8}, ...], record=True)`
4. Use clip sequences for finer control:
   - `perform_clip_sequence(events=[{"beat": 0, "action": "fire_clip", "track_name": "GEMINI TEST", "clip_index": 0}], record=True)`
5. Use `realtime=False` only for dry-run dispatch tests. Real recording needs `realtime=True`.
6. Do not call `stop_all_clips` as part of arrangement recording unless the user explicitly asks.
7. After recording, call `stop_arrangement_recording`, then read `ableton://transport`.

## Edit Existing Material

1. Read `get_clip_notes`.
2. Preserve the original clip unless the user explicitly wants replacement.
3. Write to a new destination slot with `variation` or `harmonize`.
4. Fire the destination clip only after verifying it exists.

## Mix And Automate

1. Use `list_tracks` to identify roles and names.
2. Use `set_mixer` for coarse volume, pan, mute, solo, arm, and sends.
3. Use `list_device_parameters` before `set_device_parameter` or `set_clip_envelope`.
4. Keep automation points sparse and within the parameter min/max range.

## Diagnose

1. Read `ableton://session`, `ableton://tracks`, `ableton://transport`, and `ableton://command-log`.
2. Summarize current structure and likely intent.
3. Identify missing devices, empty clips, muted/soloed tracks, stopped transport, and recent failed commands.
4. Make small changes and verify each one.
