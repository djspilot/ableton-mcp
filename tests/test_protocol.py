import json
import socket
import threading

import pytest

from MCP_Server.protocol import command_message, decode_message, encode_message
from MCP_Server.server import AbletonConnection


def test_protocol_uses_newline_delimited_json():
    payload = command_message("ping", {})

    assert payload.endswith(b"\n")
    assert json.loads(payload.decode("utf-8")) == {"type": "ping", "params": {}}
    assert decode_message(payload.rstrip(b"\n")) == {"type": "ping", "params": {}}


def test_connection_reads_one_response_line_and_keeps_buffered_data():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    host, port = server.getsockname()
    seen = []

    def handle_client():
        client, _ = server.accept()
        try:
            seen.append(client.recv(1024))
            client.sendall(
                encode_message({"status": "success", "result": {"first": True}})
                + encode_message({"status": "success", "result": {"second": True}})
            )
            seen.append(client.recv(1024))
        finally:
            client.close()
            server.close()

    thread = threading.Thread(target=handle_client)
    thread.start()
    conn = AbletonConnection(host=host, port=port)

    try:
        assert conn.send_command("first") == {"first": True}
        assert conn.send_command("second") == {"second": True}
    finally:
        conn.disconnect()
        thread.join(timeout=2)

    assert seen[0] == command_message("first", {})
    assert seen[1] == command_message("second", {})


def test_connection_disconnects_after_invalid_json_response():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    host, port = server.getsockname()

    def handle_client():
        client, _ = server.accept()
        try:
            client.recv(1024)
            client.sendall(b"{not-json}\n")
        finally:
            client.close()
            server.close()

    thread = threading.Thread(target=handle_client)
    thread.start()
    conn = AbletonConnection(host=host, port=port)

    with pytest.raises(Exception, match="Invalid response from Ableton"):
        conn.send_command("bad")

    assert conn.sock is None
    thread.join(timeout=2)
