import json
from typing import Any, Dict


def encode_message(message: Dict[str, Any]) -> bytes:
    """Encode one JSON message using newline-delimited framing."""
    return (json.dumps(message) + "\n").encode("utf-8")


def decode_message(line: bytes) -> Dict[str, Any]:
    """Decode one newline-delimited JSON message."""
    return json.loads(line.decode("utf-8"))


def command_message(command_type: str, params: Dict[str, Any]) -> bytes:
    return encode_message({"type": command_type, "params": params})
