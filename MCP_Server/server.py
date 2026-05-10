# ableton_mcp_server.py — radically expanded
# - NDJSON framing (\n-delimited JSON), per-call lock, real ping
# - mixer/transport/scenes/undo/redo/device-params/clip-envelopes
# - music-DSL helpers (patterns, harmonize, variation, morph_scene)
# - session memory file at ~/.ableton-mcp/session.json
# - event polling
from mcp.server.fastmcp import FastMCP, Context
import socket
import json
import logging
import os
import re
import functools
import threading
import time
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, List, Union, Optional

from MCP_Server.music import (
    harmonize_notes,
    make_notes,
    vary_notes,
)
from MCP_Server.arrangement import (
    apply_spec_patch,
    arrangement_presets,
    compact_plan,
    compile_scene_arrangement_spec,
    execute_timed_events,
    parse_patch_text,
    scene_sequence_to_events,
    spec_from_dsl,
)
from MCP_Server.protocol import command_message, decode_message
from MCP_Server.recipes import STYLE_RECIPES as SHARED_STYLE_RECIPES, recipe_summary

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AbletonMCPServer")

MEMORY_DIR = os.path.expanduser("~/.ableton-mcp")
MEMORY_FILE = os.path.join(MEMORY_DIR, "session.json")
DEFAULT_HOST = os.environ.get("ABLETON_MCP_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("ABLETON_MCP_PORT", "9877"))
COMMAND_LOG_LIMIT = 200
COMMAND_LOG: List[Dict[str, Any]] = []
DESTRUCTIVE_COMMANDS = {"delete_track", "delete_clip", "delete_scene", "clear_clip_envelope"}


def _log_command(command: str, params: Dict[str, Any], status: str,
                 error: Optional[str] = None) -> None:
    entry = {
        "ts": time.time(),
        "command": command,
        "params": params,
        "status": status,
        "destructive": command in DESTRUCTIVE_COMMANDS,
    }
    if error:
        entry["error"] = error
    COMMAND_LOG.append(entry)
    del COMMAND_LOG[:-COMMAND_LOG_LIMIT]


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------
@dataclass
class AbletonConnection:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    sock: Optional[socket.socket] = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    buffer: bytes = b""

    def connect(self) -> bool:
        if self.sock:
            return True
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(15.0)
            self.buffer = b""
            logger.info("Connected to Ableton at %s:%d", self.host, self.port)
            return True
        except Exception as e:
            logger.error("Failed to connect: %s", e)
            self.sock = None
            return False

    def disconnect(self):
        if self.sock:
            try: self.sock.close()
            except Exception: pass
            self.sock = None
            self.buffer = b""

    def _read_line(self, timeout: float) -> bytes:
        self.sock.settimeout(timeout)
        deadline = time.time() + timeout
        while b"\n" not in self.buffer:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise socket.timeout("read line timeout")
            self.sock.settimeout(remaining)
            chunk = self.sock.recv(8192)
            if not chunk:
                raise ConnectionError("remote closed")
            self.buffer += chunk
        line, self.buffer = self.buffer.split(b"\n", 1)
        return line

    def send_command(self, command_type: str, params: Optional[Dict[str, Any]] = None,
                     timeout: float = 15.0) -> Dict[str, Any]:
        with self.lock:
            if not self.sock and not self.connect():
                raise ConnectionError("Not connected to Ableton")
            try:
                self.sock.sendall(command_message(command_type, params or {}))
                line = self._read_line(timeout)
                response = decode_message(line)
                if response.get("status") == "error":
                    raise Exception(response.get("message", "Unknown error from Ableton"))
                return response.get("result", {})
            except (socket.timeout, ConnectionError, BrokenPipeError, ConnectionResetError) as e:
                logger.error("Socket error on %s: %s", command_type, e)
                self.disconnect()
                raise Exception("Connection to Ableton lost: " + str(e))
            except json.JSONDecodeError as e:
                logger.error("Bad JSON: %s", e)
                self.disconnect()
                raise Exception("Invalid response from Ableton")


_conn: Optional[AbletonConnection] = None
_conn_lock = threading.Lock()


def get_ableton_connection() -> AbletonConnection:
    global _conn
    with _conn_lock:
        if _conn is not None:
            try:
                _conn.send_command("ping", timeout=2.0)
                return _conn
            except Exception:
                logger.warning("Ping failed, reconnecting")
                _conn.disconnect()
                _conn = None
        for attempt in range(1, 4):
            try:
                logger.info("Connecting to Ableton (attempt %d/3)...", attempt)
                c = AbletonConnection()
                if c.connect():
                    c.send_command("ping", timeout=3.0)
                    _conn = c
                    return _conn
            except Exception as e:
                logger.error("Attempt %d failed: %s", attempt, e)
                try:
                    if 'c' in locals():
                        c.disconnect()
                except Exception:
                    pass
            time.sleep(0.5)
        raise Exception("Could not connect to Ableton. Make sure the Remote Script is loaded.")


# ---------------------------------------------------------------------------
# Server lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    logger.info("AbletonMCP server starting up")
    try:
        try:
            get_ableton_connection()
            logger.info("Connected to Ableton on startup")
        except Exception as e:
            logger.warning("Startup connect failed: %s", e)
        yield {}
    finally:
        global _conn
        if _conn:
            _conn.disconnect()
            _conn = None
        logger.info("AbletonMCP server shut down")


mcp = FastMCP("AbletonMCP", lifespan=server_lifespan)


def _wrap(fn):
    """Tool decorator that turns exceptions into readable error strings.
    Uses functools.wraps so FastMCP/Pydantic can introspect the real signature."""
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logger.exception("Tool %s failed", fn.__name__)
            return f"Error in {fn.__name__}: {e}"
    return inner


def _send(cmd: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    command_params = params or {}
    try:
        result = get_ableton_connection().send_command(cmd, command_params)
        _log_command(cmd, command_params, "success")
        return result
    except Exception as e:
        _log_command(cmd, command_params, "error", str(e))
        raise


def _j(x) -> str:
    return json.dumps(x, indent=2)


def _safe_json_resource(fetcher):
    try:
        return _j(fetcher())
    except Exception as e:
        logger.exception("Resource read failed")
        return _j({"error": str(e)})


def _compact_view(payload: Dict[str, Any], verbosity: str = "full") -> Dict[str, Any]:
    if verbosity == "compact":
        plan = payload.get("plan")
        compact = dict(payload)
        if isinstance(plan, dict):
            compact["plan"] = compact_plan(plan)
        if "events" in compact and isinstance(compact["events"], list):
            compact["event_count"] = len(compact["events"])
            del compact["events"]
        return compact
    return payload


def _plan_store_load() -> Dict[str, Any]:
    memory = _memory_load()
    plans = memory.get("arrangement_plans")
    if not isinstance(plans, dict):
        return {}
    return plans


def _plan_store_save(plans: Dict[str, Any]) -> None:
    memory = _memory_load()
    memory["arrangement_plans"] = plans
    _memory_save(memory)


# ---------------------------------------------------------------------------
# Resources expose current Live state as context without asking the model to
# choose an action-oriented tool.
# ---------------------------------------------------------------------------
@mcp.resource("ableton://session")
def session_resource() -> str:
    """Current Ableton session summary."""
    return _safe_json_resource(lambda: _send("get_session_info"))


@mcp.resource("ableton://tracks")
def tracks_resource() -> str:
    """Compact track and clip-slot summary."""
    return _safe_json_resource(lambda: _send("list_tracks"))


@mcp.resource("ableton://transport")
def transport_resource() -> str:
    """Current transport and loop state."""
    return _safe_json_resource(lambda: _send("get_transport"))


@mcp.resource("ableton://scenes")
def scenes_resource() -> str:
    """Current scene list."""
    return _safe_json_resource(lambda: _send("list_scenes"))


@mcp.resource("ableton://style-recipes")
def style_recipes_resource() -> str:
    """Built-in style recipe summaries."""
    return _j(recipe_summary())


@mcp.resource("ableton://command-log")
def command_log_resource() -> str:
    """Recent Ableton command log for debugging and recovery."""
    return _j({"commands": COMMAND_LOG[-COMMAND_LOG_LIMIT:]})


@mcp.resource("ableton://server-status")
def server_status_resource() -> str:
    """MCP server transport, safety, and connection status."""
    connected = False
    if _conn is not None and _conn.sock is not None:
        connected = True
    return _j({
        "transport": "tcp-ndjson",
        "host": DEFAULT_HOST,
        "port": DEFAULT_PORT,
        "connected": connected,
        "destructive_commands": sorted(DESTRUCTIVE_COMMANDS),
        "command_log_limit": COMMAND_LOG_LIMIT,
    })


# ---------------------------------------------------------------------------
# Prompts give clients reusable workflows that combine resources and tools.
# ---------------------------------------------------------------------------
@mcp.prompt()
def build_arrangement(style: str = "deep-house", scenes: int = 3) -> str:
    return (
        "Build an Ableton session in the '%s' style with about %d scenes. "
        "First read ableton://tracks and ableton://style-recipes. Then create missing "
        "tracks and scenes, load devices by discovery instead of guessing URIs, write "
        "patterns one cell at a time, and verify with list_tracks after structural changes."
    ) % (style, scenes)


@mcp.prompt()
def diagnose_session(goal: str = "make the session clearer and more playable") -> str:
    return (
        "Diagnose the current Ableton session for this goal: %s. Read ableton://session, "
        "ableton://tracks, ableton://transport, and ableton://command-log. Summarize what "
        "is present, identify risky or destructive edits before making them, then propose "
        "small verified changes."
    ) % goal


@mcp.prompt()
def make_clip_variation(track_index: int, source_clip: int, destination_clip: int,
                        intensity: float = 0.5) -> str:
    return (
        "Create a variation from track %d clip %d into clip %d with intensity %.2f. "
        "Read the source notes first, preserve the original clip, write to the destination "
        "with variation, then verify by reading the destination notes."
    ) % (track_index, source_clip, destination_clip, intensity)


@mcp.prompt()
def record_arrangement_plan(style: str = "current set", sections: str = "intro, verse, build, drop, outro") -> str:
    return (
        "Plan an Ableton arrangement recording for %s with sections: %s. First read "
        "ableton://tracks, ableton://scenes, and ableton://transport. Build a declarative "
        "scene arrangement spec, run preview_scene_arrangement_spec first, then run "
        "execute_scene_arrangement_spec when the timeline looks correct."
    ) % (style, sections)


@mcp.prompt()
def arrangement_spec_workflow(style: str = "current set", target_bars: int = 44) -> str:
    return (
        "Create an arrangement for %s with about %d bars using a scene arrangement spec. "
        "Read ableton://scenes and ableton://transport first. Then produce one spec JSON object "
        "with fields: start_beat, tempo(optional), record, realtime, stop_after, rewind_after, "
        "focus_view, sections[]. Each section requires scene_index and bars or duration_beats "
        "(optional label). Validate with preview_scene_arrangement_spec, then execute with "
        "execute_scene_arrangement_spec."
    ) % (style, target_bars)


@mcp.prompt()
def token_efficient_arrangement(style: str = "ukg", bpm: int = 138) -> str:
    return (
        "Use a compact DSL string instead of long JSON. Example: "
        "'style=%s; bpm=%d; template=club44; scenes=A,B,C,D; kit=909a; bass=reese2; "
        "record=true; realtime=true'. Then call parse_arrangement_dsl, "
        "preview_scene_arrangement_spec, and execute_scene_arrangement_spec."
    ) % (style, bpm)


# ---------------------------------------------------------------------------
# Read-only tools
# ---------------------------------------------------------------------------
@mcp.tool()
@_wrap
def get_session_info(ctx: Context) -> str:
    """Tempo, time signature, scene/track counts, transport state, loop region, undo/redo, master mix."""
    return _j(_send("get_session_info"))


@mcp.tool()
@_wrap
def list_tracks(ctx: Context) -> str:
    """One-shot summary of every track: index, name, mute/solo/arm, clip names per slot. Use this BEFORE get_track_info to avoid N calls."""
    return _j(_send("list_tracks"))


@mcp.tool()
@_wrap
def get_track_info(ctx: Context, track_index: int) -> str:
    """Detailed track info: clips with loop info, devices with param counts, sends."""
    return _j(_send("get_track_info", {"track_index": track_index}))


@mcp.tool()
@_wrap
def get_clip_notes(ctx: Context, track_index: int, clip_index: int) -> str:
    """Read all MIDI notes from a clip. Use this before add_notes_to_clip(mode='replace') if you want to edit existing notes."""
    return _j(_send("get_clip_notes", {"track_index": track_index, "clip_index": clip_index}))


@mcp.tool()
@_wrap
def get_transport(ctx: Context) -> str:
    """Playback/record state, position in beats, loop region, tempo, time sig."""
    return _j(_send("get_transport"))


@mcp.tool()
@_wrap
def list_scenes(ctx: Context) -> str:
    """All scenes with index/name/triggered state."""
    return _j(_send("list_scenes"))


@mcp.tool()
@_wrap
def list_device_parameters(ctx: Context, track_index: int, device_index: int) -> str:
    """List all parameters of a device with current values, ranges, and whether they're enabled. First 8 are usually macros for racks."""
    return _j(_send("list_device_parameters",
                    {"track_index": track_index, "device_index": device_index}))


@mcp.tool()
@_wrap
def get_device_parameter(ctx: Context, track_index: int, device_index: int,
                         parameter_name: Optional[str] = None,
                         parameter_index: Optional[int] = None) -> str:
    """Read one parameter by name (fuzzy) or index."""
    return _j(_send("get_device_parameter", {
        "track_index": track_index, "device_index": device_index,
        "parameter_name": parameter_name, "parameter_index": parameter_index,
    }))


# ---------------------------------------------------------------------------
# Tracks
# ---------------------------------------------------------------------------
@mcp.tool()
@_wrap
def create_midi_track(ctx: Context, index: int = -1) -> str:
    """Create a MIDI track. index=-1 appends to end."""
    r = _send("create_midi_track", {"index": index})
    return f"Created MIDI track #{r['index']}: {r['name']}"


@mcp.tool()
@_wrap
def create_audio_track(ctx: Context, index: int = -1) -> str:
    """Create an audio track."""
    r = _send("create_audio_track", {"index": index})
    return f"Created audio track #{r['index']}: {r['name']}"


@mcp.tool()
@_wrap
def delete_track(ctx: Context, track_index: int) -> str:
    """Delete a track. NOT undoable through MCP — use Live's undo if needed."""
    _send("delete_track", {"track_index": track_index})
    return f"Deleted track {track_index}"


@mcp.tool()
@_wrap
def duplicate_track(ctx: Context, track_index: int) -> str:
    """Duplicate a track and all its clips/devices."""
    r = _send("duplicate_track", {"track_index": track_index})
    return f"Duplicated track {track_index} (now {r['new_track_count']} tracks)"


@mcp.tool()
@_wrap
def set_track_name(ctx: Context, track_index: int, name: str) -> str:
    r = _send("set_track_name", {"track_index": track_index, "name": name})
    return f"Renamed track {track_index} → {r['name']}"


@mcp.tool()
@_wrap
def set_mixer(ctx: Context, track_index: Union[int, str],
              volume: Optional[float] = None,
              panning: Optional[float] = None,
              mute: Optional[bool] = None,
              solo: Optional[bool] = None,
              arm: Optional[bool] = None,
              sends: Optional[Dict[str, float]] = None) -> str:
    """Set mixer state on a track. Use track_index='master' or -1 for the master track.
    volume: 0.0–1.0 (0.85 ≈ unity), panning: -1.0..+1.0, sends: {'0': 0.5, '1': 0.0}.
    Pass only the fields you want to change."""
    params: Dict[str, Any] = {"track_index": track_index}
    for k, v in [("volume", volume), ("panning", panning), ("mute", mute),
                 ("solo", solo), ("arm", arm), ("sends", sends)]:
        if v is not None:
            params[k] = v
    return _j(_send("set_mixer", params))


# ---------------------------------------------------------------------------
# Clips
# ---------------------------------------------------------------------------
@mcp.tool()
@_wrap
def create_clip(ctx: Context, track_index: int, clip_index: int,
                length: float = 4.0, overwrite: bool = False) -> str:
    """Create an empty MIDI clip. Idempotent: if a clip already exists and overwrite=False, returns the existing clip."""
    r = _send("create_clip", {"track_index": track_index, "clip_index": clip_index,
                              "length": length, "overwrite": overwrite})
    if r.get("existed"):
        return f"Clip already existed at {track_index}/{clip_index} (length {r['length']}). Pass overwrite=True to replace."
    return f"Created clip at {track_index}/{clip_index}, length {length} beats"


@mcp.tool()
@_wrap
def delete_clip(ctx: Context, track_index: int, clip_index: int) -> str:
    _send("delete_clip", {"track_index": track_index, "clip_index": clip_index})
    return f"Deleted clip at {track_index}/{clip_index}"


@mcp.tool()
@_wrap
def duplicate_clip(ctx: Context, src_track: int, src_clip: int,
                   dst_track: Optional[int] = None, dst_clip: Optional[int] = None) -> str:
    """Duplicate a clip. Same track + dst_clip=None → next slot. Cross-track copies notes (MIDI only) into dst_clip (or first empty slot)."""
    params: Dict[str, Any] = {"src_track": src_track, "src_clip": src_clip}
    if dst_track is not None: params["dst_track"] = dst_track
    if dst_clip is not None: params["dst_clip"] = dst_clip
    return _j(_send("duplicate_clip", params))


@mcp.tool()
@_wrap
def add_notes_to_clip(ctx: Context, track_index: int, clip_index: int,
                      notes: List[Dict[str, Union[int, float, bool]]],
                      mode: str = "append") -> str:
    """Add MIDI notes to a clip.
    mode='append' (default, NON-destructive — fixed from old behavior),
    mode='replace' (wipes existing notes).
    Each note: {pitch:0-127, start_time:beats, duration:beats, velocity:0-127, mute:bool}."""
    r = _send("add_notes_to_clip", {"track_index": track_index, "clip_index": clip_index,
                                    "notes": notes, "mode": mode})
    return f"{mode}'d {r.get('added', len(notes))} notes to {track_index}/{clip_index}"


@mcp.tool()
@_wrap
def set_clip_name(ctx: Context, track_index: int, clip_index: int, name: str) -> str:
    r = _send("set_clip_name", {"track_index": track_index, "clip_index": clip_index, "name": name})
    return f"Renamed clip {track_index}/{clip_index} → {r['name']}"


@mcp.tool()
@_wrap
def set_clip_loop(ctx: Context, track_index: int, clip_index: int,
                  looping: Optional[bool] = None,
                  loop_start: Optional[float] = None,
                  loop_end: Optional[float] = None) -> str:
    """Set the loop region inside a clip (beats). Useful for shortening clips without re-creating."""
    params: Dict[str, Any] = {"track_index": track_index, "clip_index": clip_index}
    for k, v in [("looping", looping), ("loop_start", loop_start), ("loop_end", loop_end)]:
        if v is not None: params[k] = v
    return _j(_send("set_clip_loop", params))


@mcp.tool()
@_wrap
def quantize_clip(ctx: Context, track_index: int, clip_index: int,
                  grid: str = "1/16", amount: float = 1.0) -> str:
    """Quantize note start times. grid: 1/4, 1/8, 1/8t, 1/16, 1/16t, 1/32. amount: 0..1."""
    return _j(_send("quantize_clip", {"track_index": track_index, "clip_index": clip_index,
                                      "grid": grid, "amount": amount}))


# ---------------------------------------------------------------------------
# Transport / scenes
# ---------------------------------------------------------------------------
@mcp.tool()
@_wrap
def set_tempo(ctx: Context, tempo: float) -> str:
    return _j(_send("set_tempo", {"tempo": tempo}))


@mcp.tool()
@_wrap
def set_time_signature(ctx: Context, numerator: int, denominator: int) -> str:
    return _j(_send("set_time_signature", {"numerator": numerator, "denominator": denominator}))


@mcp.tool()
@_wrap
def set_metronome(ctx: Context, enabled: bool) -> str:
    return _j(_send("set_metronome", {"enabled": enabled}))


@mcp.tool()
@_wrap
def set_loop(ctx: Context, enabled: Optional[bool] = None,
             start: Optional[float] = None, length: Optional[float] = None) -> str:
    """Arrangement-view loop region. start/length in beats."""
    params = {}
    for k, v in [("enabled", enabled), ("start", start), ("length", length)]:
        if v is not None: params[k] = v
    return _j(_send("set_loop", params))


@mcp.tool()
@_wrap
def fire_clip(ctx: Context, track_index: int, clip_index: int) -> str:
    _send("fire_clip", {"track_index": track_index, "clip_index": clip_index})
    return f"Fired {track_index}/{clip_index}"


@mcp.tool()
@_wrap
def stop_clip(ctx: Context, track_index: int, clip_index: int) -> str:
    _send("stop_clip", {"track_index": track_index, "clip_index": clip_index})
    return f"Stopped {track_index}/{clip_index}"


@mcp.tool()
@_wrap
def stop_all_clips(ctx: Context) -> str:
    _send("stop_all_clips")
    return "Stopped all clips"


@mcp.tool()
@_wrap
def fire_scene(ctx: Context, scene_index: int) -> str:
    r = _send("fire_scene", {"scene_index": scene_index})
    return f"Fired scene {scene_index}: {r.get('scene')}"


@mcp.tool()
@_wrap
def create_scene(ctx: Context, index: int = -1, name: Optional[str] = None) -> str:
    params: Dict[str, Any] = {"index": index}
    if name: params["name"] = name
    r = _send("create_scene", params)
    return f"Created scene #{r['index']}: {r['name']}"


@mcp.tool()
@_wrap
def delete_scene(ctx: Context, scene_index: int) -> str:
    _send("delete_scene", {"scene_index": scene_index})
    return f"Deleted scene {scene_index}"


@mcp.tool()
@_wrap
def duplicate_scene(ctx: Context, scene_index: int) -> str:
    r = _send("duplicate_scene", {"scene_index": scene_index})
    return f"Duplicated scene {scene_index} (now {r['new_count']} scenes)"


@mcp.tool()
@_wrap
def set_scene_name(ctx: Context, scene_index: int, name: str) -> str:
    r = _send("set_scene_name", {"scene_index": scene_index, "name": name})
    return f"Renamed scene {scene_index} → {r['name']}"


@mcp.tool()
@_wrap
def start_playback(ctx: Context) -> str:
    _send("start_playback"); return "Started playback"


@mcp.tool()
@_wrap
def stop_playback(ctx: Context) -> str:
    _send("stop_playback"); return "Stopped playback"


@mcp.tool()
@_wrap
def continue_playback(ctx: Context) -> str:
    _send("continue_playback"); return "Resumed playback from current position"


@mcp.tool()
@_wrap
def set_arrangement_position(ctx: Context, beat: float) -> str:
    """Move Arrangement playback position to an absolute beat."""
    return _j(_send("jump_to_time", {"time": beat}))


@mcp.tool()
@_wrap
def set_record_mode(ctx: Context, enabled: bool) -> str:
    """Enable or disable Arrangement record mode."""
    command = "start_recording" if enabled else "stop_recording"
    return _j(_send(command))


@mcp.tool()
@_wrap
def start_arrangement_recording(ctx: Context, start_beat: float = 0.0) -> str:
    """Move to start_beat, enable Arrangement record mode, and start playback."""
    _send("jump_to_time", {"time": start_beat})
    _send("start_recording")
    return _j(_send("start_playback"))


@mcp.tool()
@_wrap
def stop_arrangement_recording(ctx: Context, stop_transport: bool = True) -> str:
    """Disable Arrangement record mode and optionally stop transport."""
    _send("stop_recording")
    if stop_transport:
        return _j(_send("stop_playback"))
    return _j(_send("get_transport"))


@mcp.tool()
@_wrap
def duplicate_clip_to_arrangement(ctx: Context, track_index: int, clip_index: int,
                                  beat: float) -> str:
    """Copy one Session View clip slot into Arrangement View at an absolute beat."""
    return _j(_send("duplicate_clip_to_arrangement", {
        "track_index": track_index,
        "clip_index": clip_index,
        "beat": beat,
    }))


@mcp.tool()
@_wrap
def duplicate_scene_to_arrangement(ctx: Context, scene_index: int, beat: float,
                                   duration_beats: Optional[float] = None) -> str:
    """Copy all clips in one Session scene into Arrangement View.
    duration_beats repeats shorter clips until the section is filled.
    """
    params: Dict[str, Any] = {"scene_index": scene_index, "beat": beat}
    if duration_beats is not None:
        params["duration_beats"] = duration_beats
    return _j(_send("duplicate_scene_to_arrangement", params))


@mcp.tool()
@_wrap
def build_arrangement_from_session(ctx: Context, sections: List[Dict[str, Any]]) -> str:
    """Build an Arrangement View song from Session scenes.
    Each section accepts: scene_index, bars or duration_beats, optional beat/start_beat, label.
    """
    return _j(_send("build_arrangement_from_session", {"sections": sections}))


@mcp.tool()
@_wrap
def list_arrangement_presets(ctx: Context) -> str:
    """List arrangement templates and preset IDs for token-efficient prompting."""
    return _j(arrangement_presets())


@mcp.tool()
@_wrap
def parse_arrangement_dsl(ctx: Context, dsl: str, verbosity: str = "compact") -> str:
    """Convert compact arrangement DSL to normalized spec.
    Example: style=ukg; bpm=138; template=club44; scenes=A,B,C,D; kit=909a; bass=reese2"""
    scene_count = int(_send("get_session_info").get("scene_count", 0))
    transport = _send("get_transport")
    tempo = float(transport.get("tempo", 120.0))
    spec = spec_from_dsl(dsl, default_tempo=tempo, scene_count=scene_count)
    payload = {
        "dsl": dsl,
        "spec": spec,
        "preview": compile_scene_arrangement_spec(spec, default_tempo=tempo),
    }
    if verbosity == "compact":
        payload["preview"] = compact_plan(payload["preview"])
    return _j(payload)


@mcp.tool()
@_wrap
def save_arrangement_plan(ctx: Context, slot: str, spec: Dict[str, Any]) -> str:
    """Save a declarative arrangement spec in server-side memory slots."""
    plans = _plan_store_load()
    plans[slot] = spec
    _plan_store_save(plans)
    return _j({"saved": True, "slot": slot, "slots": sorted(plans.keys())})


@mcp.tool()
@_wrap
def load_arrangement_plan(ctx: Context, slot: str, verbosity: str = "compact") -> str:
    """Load one arrangement spec from server-side memory."""
    plans = _plan_store_load()
    if slot not in plans:
        return _j({"error": "slot not found", "slot": slot, "slots": sorted(plans.keys())})
    spec = plans[slot]
    transport = _send("get_transport")
    default_tempo = float(transport.get("tempo", 120.0))
    plan = compile_scene_arrangement_spec(spec, default_tempo=default_tempo)
    return _j(_compact_view({"slot": slot, "spec": spec, "plan": plan}, verbosity=verbosity))


@mcp.tool()
@_wrap
def patch_arrangement_plan(ctx: Context, slot: str, patch: Union[str, Dict[str, Any]],
                           verbosity: str = "compact") -> str:
    """Patch a saved arrangement plan.
    Text patches support: 'section[2].bars=8' or 'swap scene A->C'."""
    plans = _plan_store_load()
    if slot not in plans:
        return _j({"error": "slot not found", "slot": slot, "slots": sorted(plans.keys())})
    current_spec = plans[slot]
    session_info = _send("get_session_info")
    scene_count = int(session_info.get("scene_count", 0))
    patch_obj = parse_patch_text(patch, scene_count=scene_count) if isinstance(patch, str) else patch
    updated_spec = apply_spec_patch(current_spec, patch_obj)
    plans[slot] = updated_spec
    _plan_store_save(plans)
    transport = _send("get_transport")
    default_tempo = float(transport.get("tempo", 120.0))
    plan = compile_scene_arrangement_spec(updated_spec, default_tempo=default_tempo)
    return _j(_compact_view({
        "slot": slot,
        "patch": patch_obj,
        "spec": updated_spec,
        "plan": plan,
    }, verbosity=verbosity))


def _execute_scene_spec(spec: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    transport = _send("get_transport")
    default_tempo = float(transport.get("tempo", 120.0))
    plan = compile_scene_arrangement_spec(spec, default_tempo=default_tempo)
    if dry_run:
        return {"dry_run": True, "plan": plan}

    focus_view = plan.get("focus_view")
    if focus_view:
        _send("focus_view", {"view_name": str(focus_view)})

    if plan["record"]:
        _send("jump_to_time", {"time": plan["start_beat"]})
        _send("start_recording")
        _send("start_playback")
    elif spec.get("start_playback", False):
        _send("jump_to_time", {"time": plan["start_beat"]})
        _send("start_playback")

    log = execute_timed_events(_send, plan["events"], tempo=plan["tempo"], realtime=plan["realtime"])

    if plan["record"]:
        _send("stop_recording")
    if plan["stop_after"]:
        _send("stop_playback")
    if plan["rewind_after"]:
        _send("jump_to_time", {"time": plan["start_beat"]})

    after = _send("get_session_info")
    post = {
        "is_playing": after.get("is_playing"),
        "is_recording": after.get("is_recording"),
        "current_song_time": after.get("current_song_time"),
        "can_undo": after.get("can_undo"),
    }
    return {"dry_run": False, "plan": plan, "events": log, "post_session": post}


@mcp.tool()
@_wrap
def preview_scene_arrangement_spec(ctx: Context, spec: Dict[str, Any], verbosity: str = "full") -> str:
    """Validate a declarative scene arrangement spec and return a deterministic timeline (dry-run).
    spec fields: start_beat, tempo(optional), record, realtime, stop_after, rewind_after,
    focus_view, sections[]. Each section needs scene_index plus bars or duration_beats."""
    transport = _send("get_transport")
    tempo = float(transport.get("tempo", 120.0))
    plan = compile_scene_arrangement_spec(spec, default_tempo=tempo)
    return _j(_compact_view({"plan": plan}, verbosity=verbosity))


@mcp.tool()
@_wrap
def execute_scene_arrangement_spec(ctx: Context, spec: Dict[str, Any], dry_run: bool = False,
                                   verbosity: str = "full") -> str:
    """Execute a declarative scene arrangement spec.
    Set dry_run=True to return timeline only without firing scenes or changing transport."""
    return _j(_compact_view(_execute_scene_spec(spec, dry_run=dry_run), verbosity=verbosity))


def _guess_dsl_from_goal(goal_prompt: str) -> str:
    text = goal_prompt.lower()
    if "trap" in text:
        style = "trap"
        kit = "trap808"
        bass = "subclean"
    elif "house" in text:
        style = "house"
        kit = "909a"
        bass = "reese2"
    else:
        style = "ukg"
        kit = "breaks1"
        bass = "reese2"

    bar_match = re.search(r"(\d+)\s*bars?", text)
    bars = int(bar_match.group(1)) if bar_match else 44
    if bars >= 60:
        template = "extended64"
    elif bars <= 34:
        template = "radio32"
    else:
        template = "club44"

    bpm_match = re.search(r"(\d+)\s*bpm", text)
    bpm = int(bpm_match.group(1)) if bpm_match else 138
    return (
        f"style={style}; bpm={bpm}; template={template}; scenes=A,B,C,D; "
        f"kit={kit}; bass={bass}; record=true; realtime=true"
    )


@mcp.tool()
@_wrap
def compose_arrangement(ctx: Context, goal_prompt: str = "club arrangement 44 bars",
                        dsl: Optional[str] = None, slot: str = "current",
                        mode: str = "preview", verbosity: str = "compact") -> str:
    """One-shot orchestrator: compose spec from prompt/DSL, cache it, then preview or execute."""
    mode = mode.lower().strip()
    if mode not in {"preview", "execute"}:
        raise ValueError("mode must be 'preview' or 'execute'")

    selected_dsl = dsl.strip() if dsl and dsl.strip() else _guess_dsl_from_goal(goal_prompt)
    session_info = _send("get_session_info")
    scene_count = int(session_info.get("scene_count", 0))
    transport = _send("get_transport")
    default_tempo = float(transport.get("tempo", 120.0))
    spec = spec_from_dsl(selected_dsl, default_tempo=default_tempo, scene_count=scene_count)

    plans = _plan_store_load()
    plans[slot] = spec
    _plan_store_save(plans)

    if mode == "preview":
        plan = compile_scene_arrangement_spec(spec, default_tempo=default_tempo)
        payload = {
            "mode": mode,
            "slot": slot,
            "dsl": selected_dsl,
            "spec": spec,
            "plan": plan,
        }
        return _j(_compact_view(payload, verbosity=verbosity))

    execution = _execute_scene_spec(spec, dry_run=False)
    payload = {
        "mode": mode,
        "slot": slot,
        "dsl": selected_dsl,
        "spec": spec,
        **execution,
    }
    return _j(_compact_view(payload, verbosity=verbosity))


def _resolve_track_reference(event: Dict[str, Any]) -> Dict[str, Any]:
    if "track_index" in event:
        return dict(event)
    if "track_name" not in event:
        return dict(event)
    tracks = _send("list_tracks").get("tracks", [])
    matches = [track for track in tracks if track.get("name") == event["track_name"]]
    if not matches:
        raise ValueError("Track not found: %s" % event["track_name"])
    resolved = dict(event)
    resolved["track_index"] = matches[0]["index"]
    return resolved


@mcp.tool()
@_wrap
def perform_clip_sequence(ctx: Context, events: List[Dict[str, Any]],
                          record: bool = False,
                          start_beat: float = 0.0,
                          stop_after: bool = False,
                          realtime: bool = True) -> str:
    """Perform beat-timed clip/mixer events.
    Each event: {beat, action, track_index or track_name, clip_index}. Supported actions:
    fire_clip, stop_clip, set_mixer. Set record=True to record the performance into Arrangement View."""
    transport = _send("get_transport")
    tempo = float(transport.get("tempo", 120.0))
    resolved_events = [_resolve_track_reference(event) for event in events]
    if record:
        _send("jump_to_time", {"time": start_beat})
        _send("start_recording")
        _send("start_playback")
    log = execute_timed_events(_send, resolved_events, tempo=tempo, realtime=realtime)
    if record:
        _send("stop_recording")
    if stop_after:
        _send("stop_playback")
    return _j({"tempo": tempo, "recorded": record, "events": log})


@mcp.tool()
@_wrap
def perform_scene_sequence(ctx: Context, sequence: List[Dict[str, Any]],
                           record: bool = False,
                           start_beat: float = 0.0,
                           stop_after: bool = False,
                           realtime: bool = True) -> str:
    """Perform a scene sequence. Each section: {scene_index, bars, label?}.
    bars controls the wait before the next scene. Set record=True to capture into Arrangement View."""
    events = scene_sequence_to_events(sequence)
    if start_beat:
        for event in events:
            event["beat"] += start_beat
    transport = _send("get_transport")
    tempo = float(transport.get("tempo", 120.0))
    if record:
        _send("jump_to_time", {"time": start_beat})
        _send("start_recording")
        _send("start_playback")
    log = execute_timed_events(_send, events, tempo=tempo, realtime=realtime)
    if record:
        _send("stop_recording")
    if stop_after:
        _send("stop_playback")
    return _j({"tempo": tempo, "recorded": record, "events": log})


@mcp.tool()
@_wrap
def undo(ctx: Context) -> str:
    return _j(_send("undo"))


@mcp.tool()
@_wrap
def redo(ctx: Context) -> str:
    return _j(_send("redo"))


# ---------------------------------------------------------------------------
# Devices / automation
# ---------------------------------------------------------------------------
@mcp.tool()
@_wrap
def set_device_parameter(ctx: Context, track_index: int, device_index: int,
                         value: float,
                         parameter_name: Optional[str] = None,
                         parameter_index: Optional[int] = None) -> str:
    """Set ONE device parameter. Find names via list_device_parameters first.
    For racks, params 0–7 are typically the macros."""
    return _j(_send("set_device_parameter", {
        "track_index": track_index, "device_index": device_index,
        "parameter_name": parameter_name, "parameter_index": parameter_index,
        "value": value,
    }))


@mcp.tool()
@_wrap
def set_clip_envelope(ctx: Context, track_index: int, clip_index: int,
                      device_index: int,
                      points: List[Dict[str, float]],
                      parameter_name: Optional[str] = None,
                      parameter_index: Optional[int] = None) -> str:
    """Write an automation envelope inside a clip for a device parameter.
    points: [{time: beats_from_clip_start, value: param_value}, ...].
    Existing envelope on this parameter is cleared first."""
    return _j(_send("set_clip_envelope", {
        "track_index": track_index, "clip_index": clip_index,
        "device_index": device_index,
        "parameter_name": parameter_name, "parameter_index": parameter_index,
        "points": points,
    }))


@mcp.tool()
@_wrap
def clear_clip_envelope(ctx: Context, track_index: int, clip_index: int,
                        device_index: int,
                        parameter_name: Optional[str] = None,
                        parameter_index: Optional[int] = None) -> str:
    return _j(_send("clear_clip_envelope", {
        "track_index": track_index, "clip_index": clip_index,
        "device_index": device_index,
        "parameter_name": parameter_name, "parameter_index": parameter_index,
    }))


# ---------------------------------------------------------------------------
# Browser
# ---------------------------------------------------------------------------
@mcp.tool()
@_wrap
def get_browser_tree(ctx: Context, category_type: str = "all", max_depth: int = 2) -> str:
    """Browser categories with REAL recursion. max_depth controls how deep we recurse (default 2)."""
    return _j(_send("get_browser_tree", {"category_type": category_type, "max_depth": max_depth}))


@mcp.tool()
@_wrap
def get_browser_items_at_path(ctx: Context, path: str) -> str:
    """List items at a browser path like 'instruments/Wavetable' or 'drums/Drum Rack'."""
    return _j(_send("get_browser_items_at_path", {"path": path}))


@mcp.tool()
@_wrap
def load_browser_item(ctx: Context, track_index: int, item_uri: str, clip_index: int = -1) -> str:
    r = _send("load_browser_item", {"track_index": track_index,
                                    "clip_index": clip_index, "item_uri": item_uri})
    target = f"track {track_index}" + (f", slot {clip_index}" if clip_index >= 0 else "")
    return f"Loaded '{r.get('item_name')}' onto {target}" if r.get("loaded") else f"Failed to load onto {target}"


@mcp.tool()
@_wrap
def load_drum_kit(ctx: Context, track_index: int, rack_uri: str, kit_path: str) -> str:
    """Load a drum rack then load the first loadable kit found at kit_path."""
    r = _send("load_browser_item", {"track_index": track_index, "item_uri": rack_uri})
    if not r.get("loaded"):
        return f"Failed to load drum rack {rack_uri}"
    kit = _send("get_browser_items_at_path", {"path": kit_path})
    items = kit.get("items", [])
    loadable = [i for i in items if i.get("is_loadable")]
    if not loadable:
        return f"Drum rack loaded but no loadable kit at {kit_path}"
    r2 = _send("load_browser_item", {"track_index": track_index, "item_uri": loadable[0]["uri"]})
    return f"Loaded drum rack and kit '{loadable[0]['name']}' on track {track_index}"


@mcp.tool()
@_wrap
def load_device_by_name(ctx: Context, track_index: int, device_name: str,
                        category: str = "audio_effects") -> str:
    search = _send("get_browser_items_at_path", {"path": category})
    items = search.get("items", [])
    target = next((i for i in items if device_name.lower() in i.get("name", "").lower()), None)
    if not target:
        return f"Could not find device '{device_name}' in '{category}'."
    r = _send("load_browser_item", {"track_index": track_index, "item_uri": target["uri"]})
    return f"Loaded '{target['name']}' on track {track_index}" if r.get("loaded") else "Failed to load"


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------
@mcp.tool()
@_wrap
def poll_events(ctx: Context, since: int = 0, max: int = 100) -> str:
    """Poll for events that have occurred (playback start/stop, tempo change, song time).
    Pass `since` = previous response's `latest_seq` to get only new events.
    Use this to react to user actions in Live."""
    return _j(_send("poll_events", {"since": since, "max": max}))


# ---------------------------------------------------------------------------
# Session memory
# ---------------------------------------------------------------------------
def _memory_load() -> Dict[str, Any]:
    if not os.path.isfile(MEMORY_FILE):
        return {}
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _memory_save(d: Dict[str, Any]) -> None:
    os.makedirs(MEMORY_DIR, exist_ok=True)
    with open(MEMORY_FILE, "w") as f:
        json.dump(d, f, indent=2)


@mcp.tool()
@_wrap
def session_memory_get(ctx: Context, key: Optional[str] = None) -> str:
    """Read persistent session memory. Pass key for one entry, omit for everything.
    Use for: storing track roles ('1'='drums', '2'='bass'), key/scale, current section."""
    d = _memory_load()
    return _j(d.get(key) if key else d)


@mcp.tool()
@_wrap
def session_memory_set(ctx: Context, key: str, value: Any) -> str:
    """Write to persistent session memory. value can be any JSON-serialisable thing."""
    d = _memory_load()
    d[key] = value
    _memory_save(d)
    return f"Saved memory[{key}] = {json.dumps(value)[:80]}"


@mcp.tool()
@_wrap
def session_memory_delete(ctx: Context, key: str) -> str:
    d = _memory_load()
    if key in d:
        del d[key]
        _memory_save(d)
        return f"Deleted memory[{key}]"
    return f"No such key: {key}"


# ---------------------------------------------------------------------------
# Music DSL - composes notes locally and sends via add_notes_to_clip
# ---------------------------------------------------------------------------
@mcp.tool()
@_wrap
def make_pattern(ctx: Context, track_index: int, clip_index: int, style: str,
                 bars: int = 1, key: str = "C", scale: str = "minor",
                 octave: int = 4, mode: str = "replace",
                 humanize: bool = True, seed: Optional[int] = None) -> str:
    """Generate musical content into a clip.
    style: four-on-floor, breakbeat/amen, trap, reese, arp, chord-stab.
    For drum patterns, the track must contain a Drum Rack with standard GM mapping (kick=C1, snare=D1, hh=F#1).
    For melodic patterns (arp, chord-stab, reese), supply key + scale.
    Creates the clip if it doesn't exist (length = bars * 4 beats)."""
    try:
        notes = make_notes(style, bars=bars, key=key, scale=scale, octave=octave,
                           humanize_notes=humanize, seed=seed)
    except ValueError as e:
        return str(e)
    _send("create_clip", {"track_index": track_index, "clip_index": clip_index,
                          "length": float(bars * 4), "overwrite": False})
    _send("add_notes_to_clip", {"track_index": track_index, "clip_index": clip_index,
                                "notes": notes, "mode": mode})
    return f"Wrote {style} ({bars} bar/s, {len(notes)} notes, mode={mode}) to {track_index}/{clip_index}"


@mcp.tool()
@_wrap
def variation(ctx: Context, track_index: int, src_clip: int, dst_clip: int,
              intensity: float = 0.5, seed: Optional[int] = None) -> str:
    """Read notes from src_clip and write a variation to dst_clip on the same track.
    intensity 0..1: 0 = exact copy, 1 = many octave jumps, ghost notes, missing notes."""
    src = _send("get_clip_notes", {"track_index": track_index, "clip_index": src_clip})
    out = vary_notes(src.get("notes", []), intensity=intensity, seed=seed)
    _send("create_clip", {"track_index": track_index, "clip_index": dst_clip,
                          "length": src.get("clip_length", 4.0), "overwrite": True})
    _send("add_notes_to_clip", {"track_index": track_index, "clip_index": dst_clip,
                                "notes": out, "mode": "replace"})
    return f"Wrote variation (intensity {intensity}, {len(out)} notes) to {track_index}/{dst_clip}"


@mcp.tool()
@_wrap
def harmonize(ctx: Context, src_track: int, src_clip: int,
              dst_track: int, dst_clip: int,
              key: str = "C", scale: str = "minor",
              interval: str = "third") -> str:
    """Read melody from src_clip and write a harmony part to dst_clip.
    interval: third, fifth, octave_down, sixth. Snaps to scale tones."""
    src = _send("get_clip_notes", {"track_index": src_track, "clip_index": src_clip})
    out = harmonize_notes(src.get("notes", []), key=key, scale=scale, interval=interval)
    _send("create_clip", {"track_index": dst_track, "clip_index": dst_clip,
                          "length": src.get("clip_length", 4.0), "overwrite": True})
    _send("add_notes_to_clip", {"track_index": dst_track, "clip_index": dst_clip,
                                "notes": out, "mode": "replace"})
    return f"Harmonized {src_track}/{src_clip} → {dst_track}/{dst_clip} ({interval} in {key} {scale})"


@mcp.tool()
@_wrap
def morph_scene(ctx: Context, from_scene: int, to_scene: int,
                bars: int = 8,
                track_indices: Optional[List[int]] = None,
                steps: int = 16) -> str:
    """Build automation that smoothly morphs mixer volumes from one scene's setup to another.
    Reads current volume of the specified tracks (default: all), then writes envelopes...
    Note: Live's session view doesn't have arrangement-style automation per scene, so this
    instead inserts a series of `set_mixer` calls timed via the playhead — best used while
    the destination scene is firing.

    SIMPLER variant: this just fires the destination scene right now and returns a hint
    that for true morphing, set_clip_envelope on macros is the way.
    """
    # For now, document the limit and fire the scene; the real morph is via clip envelopes.
    _send("fire_scene", {"scene_index": to_scene})
    return (f"Fired scene {to_scene}. For real morphing, use set_clip_envelope on a "
            f"Drum Buss/Filter macro inside the clips of scene {to_scene}.")


# ---------------------------------------------------------------------------
# Style recipes - shared catalog lives in MCP_Server.recipes
# ---------------------------------------------------------------------------
@mcp.tool()
@_wrap
def list_style_recipes(ctx: Context) -> str:
    """Show all built-in style recipes with their descriptions."""
    return _j(recipe_summary())


@mcp.tool()
@_wrap
def style_recipe(ctx: Context, style: str) -> str:
    """Return a structured recipe (tracks, devices, scenes, patterns, mixer hints) for a style.
    Use this BEFORE building — read the recipe, then execute it step by step with create/load/make_pattern tools.
    Available: uk-bassline, trap, deep-house. List all via list_style_recipes."""
    r = SHARED_STYLE_RECIPES.get(style.lower())
    if not r:
        return f"Unknown style '{style}'. Available: {', '.join(sorted(SHARED_STYLE_RECIPES.keys()))}"
    return _j(r)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    mcp.run()


if __name__ == "__main__":
    main()
