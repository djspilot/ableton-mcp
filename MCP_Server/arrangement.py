import time
from typing import Any, Callable, Dict, Iterable, List, Optional


ARRANGEMENT_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "club44": {
        "description": "44-bar club arrangement with steady energy lift",
        "bars": [4, 4, 4, 8, 8, 4, 8, 4],
    },
    "radio32": {
        "description": "32-bar compact radio arrangement",
        "bars": [8, 8, 8, 8],
    },
    "extended64": {
        "description": "64-bar extended DJ arrangement",
        "bars": [8, 8, 16, 16, 8, 8],
    },
}

PRESET_IDS: Dict[str, Dict[str, str]] = {
    "kit": {
        "909a": "909-inspired club drum kit",
        "breaks1": "Classic breakbeat starter kit",
        "trap808": "Trap-oriented 808 kit",
    },
    "bass": {
        "reese2": "Modern wide reese bass",
        "subclean": "Clean mono sub bass",
        "acid1": "Acid-style resonant bassline",
    },
}


def beats_to_seconds(beats: float, tempo: float) -> float:
    return float(beats) * 60.0 / float(tempo)


def sorted_events(events: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted((dict(event) for event in events), key=lambda event: float(event.get("beat", 0.0)))


def scene_sequence_to_events(sequence: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    beat = 0.0
    events = []
    for section in sequence:
        if "scene_index" not in section:
            raise ValueError("Each section needs scene_index")
        events.append({
            "beat": beat,
            "action": "fire_scene",
            "scene_index": int(section["scene_index"]),
            "label": section.get("label"),
        })
        beat += float(section.get("bars", 4)) * 4.0
    return events


def _section_duration_beats(section: Dict[str, Any]) -> float:
    if "duration_beats" in section:
        duration_beats = float(section["duration_beats"])
    else:
        duration_beats = float(section.get("bars", 4)) * 4.0
    if duration_beats <= 0:
        raise ValueError("Section duration must be > 0 beats")
    return duration_beats


def _to_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def _parse_dsl(dsl: str) -> Dict[str, str]:
    parts = [part.strip() for part in dsl.split(";") if part.strip()]
    data: Dict[str, str] = {}
    for part in parts:
        if "=" not in part:
            raise ValueError(f"Invalid DSL part (missing '='): {part}")
        key, value = part.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        if not key:
            raise ValueError("DSL key cannot be empty")
        data[key] = value
    return data


def _scene_token_to_index(token: str, scene_count: Optional[int]) -> int:
    token = token.strip()
    if not token:
        raise ValueError("Scene token cannot be empty")
    if token.lstrip("-").isdigit():
        return int(token)
    if len(token) == 1 and token.isalpha():
        index = ord(token.upper()) - ord("A")
        if index < 0:
            raise ValueError(f"Invalid scene token: {token}")
        if scene_count and scene_count > 0:
            return index % scene_count
        return index
    raise ValueError(f"Unsupported scene token: {token}")


def _parse_bar_list(raw: str) -> List[float]:
    normalized = raw.replace(",", "-")
    values = [value.strip() for value in normalized.split("-") if value.strip()]
    if not values:
        raise ValueError("form must include at least one bar length")
    bars = [float(value) for value in values]
    if any(value <= 0 for value in bars):
        raise ValueError("form bars must all be > 0")
    return bars


def arrangement_presets() -> Dict[str, Any]:
    return {
        "templates": ARRANGEMENT_TEMPLATES,
        "preset_ids": PRESET_IDS,
        "dsl_example": "style=ukg; bpm=138; template=club44; scenes=A,B,C,D; record=true; realtime=true",
    }


def spec_from_dsl(dsl: str, default_tempo: float = 120.0, scene_count: Optional[int] = None) -> Dict[str, Any]:
    fields = _parse_dsl(dsl)
    template_id = fields.get("template", "").strip().lower()
    template = ARRANGEMENT_TEMPLATES.get(template_id) if template_id else None

    if template:
        bars = [float(value) for value in template["bars"]]
    elif "form" in fields:
        bars = _parse_bar_list(fields["form"])
    else:
        bars = [4.0, 4.0, 8.0, 8.0]

    raw_scene_tokens = fields.get("scenes", "A,B,C,D")
    scene_tokens = [token.strip() for token in raw_scene_tokens.split(",") if token.strip()]
    if not scene_tokens:
        scene_tokens = ["A", "B", "C", "D"]
    scene_indices = [_scene_token_to_index(token, scene_count) for token in scene_tokens]

    sections = []
    for index, bar_count in enumerate(bars):
        scene_index = scene_indices[index % len(scene_indices)]
        sections.append({
            "scene_index": scene_index,
            "bars": bar_count,
            "label": "S%d" % (index + 1),
        })

    tempo = float(fields.get("tempo", fields.get("bpm", default_tempo)))
    if tempo <= 0:
        raise ValueError("tempo/bpm must be > 0")

    style = fields.get("style", "custom")
    energy = fields.get("energy", "flat")
    kit = fields.get("kit")
    bass = fields.get("bass")

    return {
        "tempo": tempo,
        "start_beat": float(fields.get("start_beat", fields.get("start", 0.0))),
        "record": _to_bool(fields.get("record"), True),
        "realtime": _to_bool(fields.get("realtime"), True),
        "stop_after": _to_bool(fields.get("stop_after"), True),
        "rewind_after": _to_bool(fields.get("rewind_after"), False),
        "focus_view": fields.get("focus_view", "Arranger"),
        "style": style,
        "energy": energy,
        "template_id": template_id or None,
        "preset_ids": {"kit": kit, "bass": bass},
        "sections": sections,
        "dsl": dsl,
    }


def apply_spec_patch(spec: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(spec, dict):
        raise ValueError("spec must be an object")
    if not isinstance(patch, dict):
        raise ValueError("patch must be an object")

    patched = dict(spec)
    patched_sections = [dict(section) for section in patched.get("sections", [])]
    patched["sections"] = patched_sections

    op = patch.get("op", "set")
    if op == "set":
        path = str(patch.get("path", "")).strip()
        if not path:
            raise ValueError("set patch requires path")
        value = patch.get("value")
        if path.startswith("section[") and "]." in path:
            index_part, field_name = path.split("].", 1)
            index = int(index_part[len("section["):])
            if index < 0 or index >= len(patched_sections):
                raise ValueError("section index out of range")
            patched_sections[index][field_name] = value
        else:
            patched[path] = value
    elif op == "swap_scene":
        old_scene = int(patch["old_scene"])
        new_scene = int(patch["new_scene"])
        for section in patched_sections:
            if int(section.get("scene_index", -1)) == old_scene:
                section["scene_index"] = new_scene
    elif op == "replace_sections":
        sections = patch.get("sections")
        if not isinstance(sections, list) or not sections:
            raise ValueError("replace_sections requires non-empty sections")
        patched["sections"] = [dict(section) for section in sections]
    else:
        raise ValueError("Unsupported patch op: %s" % op)
    return patched


def parse_patch_text(patch_text: str, scene_count: Optional[int] = None) -> Dict[str, Any]:
    text = patch_text.strip()
    if not text:
        raise ValueError("patch text cannot be empty")
    if text.startswith("section[") and "=" in text:
        path, value_text = text.split("=", 1)
        value_text = value_text.strip()
        lowered_path = path.strip().lower()
        if lowered_path.endswith(".scene_index"):
            value: Any = _scene_token_to_index(value_text, scene_count)
        elif lowered_path.endswith(".bars") or lowered_path.endswith(".duration_beats"):
            value = float(value_text)
        elif value_text.lower() in {"true", "false"}:
            value = _to_bool(value_text, False)
        elif value_text.replace(".", "", 1).lstrip("-").isdigit():
            value = float(value_text) if "." in value_text else int(value_text)
        else:
            value = value_text
        return {"op": "set", "path": path.strip(), "value": value}

    normalized = text.lower()
    if normalized.startswith("swap scene ") and "->" in normalized:
        raw_old, raw_new = text[len("swap scene "):].split("->", 1)
        return {
            "op": "swap_scene",
            "old_scene": _scene_token_to_index(raw_old.strip(), scene_count),
            "new_scene": _scene_token_to_index(raw_new.strip(), scene_count),
        }
    raise ValueError("Unsupported patch text")


def compact_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    timeline = plan.get("timeline", [])
    return {
        "tempo": plan.get("tempo"),
        "start_beat": plan.get("start_beat"),
        "total_bars": plan.get("total_bars"),
        "total_seconds": plan.get("total_seconds"),
        "record": plan.get("record"),
        "realtime": plan.get("realtime"),
        "sections": len(timeline),
        "scene_order": [row.get("scene_index") for row in timeline],
    }


def compile_scene_arrangement_spec(spec: Dict[str, Any], default_tempo: float = 120.0) -> Dict[str, Any]:
    if not isinstance(spec, dict):
        raise ValueError("spec must be an object")

    raw_sections = spec.get("sections")
    if not isinstance(raw_sections, list) or not raw_sections:
        raise ValueError("spec.sections must be a non-empty list")

    tempo = float(spec.get("tempo", default_tempo))
    if tempo <= 0:
        raise ValueError("tempo must be > 0")

    start_beat = float(spec.get("start_beat", 0.0))
    if start_beat < 0:
        raise ValueError("start_beat must be >= 0")

    sequence: List[Dict[str, Any]] = []
    timeline: List[Dict[str, Any]] = []
    cursor = float(start_beat)

    for index, section in enumerate(raw_sections):
        if not isinstance(section, dict):
            raise ValueError(f"Section {index} must be an object")
        if "scene_index" not in section:
            raise ValueError(f"Section {index} needs scene_index")

        scene_index = int(section["scene_index"])
        duration_beats = _section_duration_beats(section)
        duration_bars = duration_beats / 4.0
        label = section.get("label") or f"Scene {scene_index}"

        sequence.append({
            "scene_index": scene_index,
            "bars": duration_bars,
            "label": label,
        })
        timeline.append({
            "index": index,
            "scene_index": scene_index,
            "label": label,
            "start_beat": cursor,
            "duration_beats": duration_beats,
            "duration_bars": duration_bars,
            "start_seconds": beats_to_seconds(cursor - start_beat, tempo),
            "duration_seconds": beats_to_seconds(duration_beats, tempo),
        })
        cursor += duration_beats

    events = scene_sequence_to_events(sequence)
    for event in events:
        event["beat"] += start_beat

    total_beats = cursor - start_beat
    return {
        "tempo": tempo,
        "start_beat": start_beat,
        "end_beat": cursor,
        "total_beats": total_beats,
        "total_bars": total_beats / 4.0,
        "total_seconds": beats_to_seconds(total_beats, tempo),
        "record": bool(spec.get("record", True)),
        "realtime": bool(spec.get("realtime", True)),
        "stop_after": bool(spec.get("stop_after", True)),
        "rewind_after": bool(spec.get("rewind_after", False)),
        "focus_view": spec.get("focus_view", "Arranger"),
        "sequence": sequence,
        "timeline": timeline,
        "events": events,
    }


def execute_timed_events(send: Callable[[str, Optional[Dict[str, Any]]], Dict[str, Any]],
                         events: Iterable[Dict[str, Any]],
                         tempo: float,
                         realtime: bool = True) -> List[Dict[str, Any]]:
    previous_beat = 0.0
    log = []
    for event in sorted_events(events):
        beat = float(event.get("beat", 0.0))
        if realtime and beat > previous_beat:
            time.sleep(beats_to_seconds(beat - previous_beat, tempo))
        previous_beat = beat
        action = event.get("action")
        if action == "fire_clip":
            params = {"track_index": event["track_index"], "clip_index": event["clip_index"]}
        elif action == "stop_clip":
            params = {"track_index": event["track_index"], "clip_index": event["clip_index"]}
        elif action == "fire_scene":
            params = {"scene_index": event["scene_index"]}
        elif action == "set_mixer":
            params = {"track_index": event["track_index"]}
            for key in ["volume", "panning", "mute", "solo", "arm", "sends"]:
                if key in event:
                    params[key] = event[key]
        else:
            raise ValueError("Unsupported sequence action: %s" % action)
        result = send(action, params)
        log.append({"beat": beat, "action": action, "params": params, "result": result})
    return log
