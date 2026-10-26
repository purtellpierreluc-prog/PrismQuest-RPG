from types import SimpleNamespace
from unittest.mock import Mock, patch

from uvicorn.protocols.websockets.wsproto_impl import WSProtocol
from wsproto.connection import ConnectionState

from steam_client.transport import DesktopWebSocketProtocol


def test_peer_closed_transport_can_be_shutdown_idempotently():
    protocol = object.__new__(DesktopWebSocketProtocol)
    protocol.conn = SimpleNamespace(state=ConnectionState.CLOSED)
    protocol.stop_keepalive = Mock()
    protocol.transport = Mock()
    timer = protocol.close_timer = Mock()
    protocol.shutdown()
    protocol.shutdown()
    timer.cancel.assert_called_once()
    assert protocol.close_timer is None
    assert protocol.transport.close.call_count == 2


def test_live_transport_still_uses_normal_websocket_shutdown():
    protocol = object.__new__(DesktopWebSocketProtocol)
    protocol.conn = SimpleNamespace(state=ConnectionState.OPEN)
    with patch.object(WSProtocol, 'shutdown') as shutdown:
        protocol.shutdown()
    shutdown.assert_called_once()
