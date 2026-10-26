"""Desktop window preferences, kept separate from game saves."""

import asyncio
import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

LOGGER = logging.getLogger(__name__)
MIN_WINDOW_SIZE = (1000, 660)


@dataclass
class DisplayPreferences:
    width: int = 1360
    height: int = 900
    fullscreen: bool = False
    reduce_motion: bool = False

    @classmethod
    def from_payload(cls, payload):
        if not isinstance(payload, dict):
            return cls()
        try:
            width, height = int(payload.get('width', 1360)), int(payload.get('height', 900))
        except (TypeError, ValueError, OverflowError):
            return cls()
        return cls(min(7680, max(MIN_WINDOW_SIZE[0], width)), min(4320, max(MIN_WINDOW_SIZE[1], height)), payload.get('fullscreen') is True, payload.get('reduce_motion') is True)


def screen_work_area():
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        rect = wintypes.RECT()
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
            return rect.right - rect.left, rect.bottom - rect.top
    return 1920, 1080


class DesktopDisplay:
    def __init__(self, path, native=None, work_area=None):
        self.path = Path(path)
        self.native = native
        self.pending = None
        self.maximized = False
        try:
            payload = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            payload = {}
        self.preferences = DisplayPreferences.from_payload(payload)
        width, height = work_area or screen_work_area()
        self.preferences.width = min(self.preferences.width, max(MIN_WINDOW_SIZE[0], width - 32))
        self.preferences.height = min(self.preferences.height, max(MIN_WINDOW_SIZE[1], height - 32))

    @property
    def available(self):
        return self.native is not None

    @property
    def size(self):
        return self.preferences.width, self.preferences.height

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.path.parent, prefix='.display-', suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(json.dumps(asdict(self.preferences)).encode('utf-8'))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()

    def _queue_save(self):
        if self.pending is not None:
            self.pending.cancel()
        try:
            self.pending = asyncio.get_running_loop().call_later(0.4, self._safe_save)
        except RuntimeError:
            self._safe_save()

    def _safe_save(self):
        self.pending = None
        try:
            self.save()
        except OSError:
            LOGGER.exception('Could not save desktop display preferences.')

    def resized(self, event):
        if self.preferences.fullscreen or self.maximized:
            return
        width, height = event.args.get('width'), event.args.get('height')
        if not isinstance(width, (int, float)) or not isinstance(height, (int, float)) or width < MIN_WINDOW_SIZE[0] or height < MIN_WINDOW_SIZE[1]:
            return
        updated = DisplayPreferences.from_payload({'width': width, 'height': height})
        self.preferences.width, self.preferences.height = updated.width, updated.height
        self._queue_save()

    def toggle_fullscreen(self):
        window = getattr(self.native, 'main_window', None)
        if window is None:
            return
        window.toggle_fullscreen()
        self.preferences.fullscreen = not self.preferences.fullscreen
        self._queue_save()

    def set_reduce_motion(self, value):
        self.preferences.reduce_motion = bool(value)
        self._queue_save()

    def bind(self):
        self.native.on('resized', self.resized)
        self.native.on('maximized', lambda _event: setattr(self, 'maximized', True))
        self.native.on('restored', lambda _event: setattr(self, 'maximized', False))

    def flush(self):
        if self.pending is not None:
            self.pending.cancel()
            self.pending = None
        self._safe_save()
