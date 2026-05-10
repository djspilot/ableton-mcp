import time
from typing import Any, Callable, Dict, Iterable, List, Optional


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
