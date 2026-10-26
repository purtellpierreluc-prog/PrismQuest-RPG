from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from nicegui import app, ui

from steam_client import runtime


def test_native_smoke_without_window_validation_cannot_report_success(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, 'load_game', lambda _paths: SimpleNamespace(flush_desktop_save=lambda: None))
    monkeypatch.setattr(ui, 'run', Mock())
    monkeypatch.setattr(app, 'on_shutdown', Mock())
    # Browser mode intentionally skips native loading; even a clean mocked
    # ui.run return must not be accepted as native validation evidence.
    with pytest.raises(RuntimeError, match='validation failed or timed out'):
        runtime.launch(['--browser', '--native-smoke', '--data-dir', str(tmp_path)])
