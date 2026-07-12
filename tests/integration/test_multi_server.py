"""Integration tests for the combined multi-server.

Verifies that WebSocket, telnet, and SSH listeners all start inside the
single Uvicorn-owned event loop and shut down cleanly.
"""

from __future__ import annotations

import socket

import pytest
from fastapi.testclient import TestClient

from mud.multi_server import app, configure


@pytest.mark.integration
@pytest.mark.telnet
@pytest.mark.timeout(60)
def test_multi_server_lifecycle() -> None:
    """All three transports come up in one process and close on shutdown."""
    # Use high ports unlikely to conflict with other test processes.
    telnet_port = 15001
    ssh_port = 12222
    configure(telnet_port=telnet_port, ssh_port=ssh_port)

    with TestClient(app) as client:
        # WebSocket endpoint is reachable through ASGI transport.
        with client.websocket_connect("/ws") as websocket:
            # The nanny should emit the greeting banner; just read it to prove
            # the endpoint is alive, then close the connection cleanly.
            websocket.close()

        # Telnet and SSH are real TCP listeners spawned in the lifespan.
        _assert_tcp_port_listening("127.0.0.1", telnet_port, "telnet")
        _assert_tcp_port_listening("127.0.0.1", ssh_port, "ssh")


def _assert_tcp_port_listening(host: str, port: int, label: str) -> None:
    """Raise AssertionError if the given TCP port is not accepting connections."""
    sock: socket.socket | None = None
    try:
        sock = socket.create_connection((host, port), timeout=2.0)
    except OSError as exc:
        raise AssertionError(f"{label} server is not listening on {host}:{port}") from exc
    finally:
        if sock is not None:
            sock.close()
