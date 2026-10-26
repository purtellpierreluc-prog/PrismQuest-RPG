"""Compatibility for a peer-close/shutdown race in the pinned Uvicorn transport."""

from uvicorn.config import WS_PROTOCOLS
from uvicorn.protocols.websockets.wsproto_impl import WSProtocol
from wsproto.connection import ConnectionState


class DesktopWebSocketProtocol(WSProtocol):
    def shutdown(self):
        if self.conn.state == ConnectionState.CLOSED:
            self.stop_keepalive()
            if self.close_timer is not None:
                self.close_timer.cancel()
                self.close_timer = None
            self.transport.close()
            return
        super().shutdown()


def install_desktop_transport():
    WS_PROTOCOLS['wsproto'] = DesktopWebSocketProtocol
