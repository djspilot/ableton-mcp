# Safety And Recovery

## Destructive Tools

These tools can remove or overwrite session content:

- `delete_track`
- `delete_clip`
- `delete_scene`
- `clear_clip_envelope`
- `create_clip(..., overwrite=True)`
- `add_notes_to_clip(..., mode="replace")`

Before using them, state the exact target and why it is needed. Prefer duplicating or writing to a new slot when possible.

## Local Server Security

AbletonMCP is a local MCP server and talks to a local Ableton Remote Script. Keep transport bound to localhost unless explicitly developing a remote setup. Do not expose the socket to untrusted networks.

## Recovery

1. Read `ableton://command-log`.
2. If a destructive command was recent and the user wants to reverse it, use `undo`.
3. Re-read `list_tracks` and `get_session_info` after recovery.
4. If the socket fails, restart the MCP server and reload the Ableton Remote Script.
