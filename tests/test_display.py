import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from steam_client.display import DesktopDisplay, DisplayPreferences
from steam_client.storage import AtomicSaveStore, SaveRecoveryRequired


@pytest.mark.parametrize('payload', [None, [], 'bad', {'width': 'bad'}, {'height': float('inf')}])
def test_invalid_display_preferences_use_defaults(payload):
    assert DisplayPreferences.from_payload(payload) == DisplayPreferences()


def test_display_preferences_have_safe_bounds():
    assert DisplayPreferences.from_payload({'width': -10, 'height': 50000, 'fullscreen': 'true'}) == DisplayPreferences(1000, 4320, False)


def test_window_is_clamped_to_current_monitor(tmp_path):
    path = tmp_path / 'display.json'
    path.write_text(json.dumps({'width': 5000, 'height': 3500, 'fullscreen': True}))
    display = DesktopDisplay(path, work_area=(1366, 720))
    assert display.size == (1334, 688)
    assert display.preferences.fullscreen


def test_display_settings_persist_without_game_save_writes(tmp_path):
    native = SimpleNamespace(main_window=Mock(), on=Mock())
    display = DesktopDisplay(tmp_path / 'display.json', native=native)
    display.resized(SimpleNamespace(args={'width': 1200, 'height': 800}))
    display.toggle_fullscreen()
    display.flush()
    native.main_window.toggle_fullscreen.assert_called_once()
    reloaded = DesktopDisplay(display.path)
    assert reloaded.size == (1200, 800)
    assert reloaded.preferences.fullscreen
    assert not list(tmp_path.glob('.display-*.tmp'))


def test_minimized_or_fullscreen_sizes_do_not_replace_windowed_size(tmp_path):
    display = DesktopDisplay(tmp_path / 'display.json')
    expected = display.size
    display.resized(SimpleNamespace(args={'width': 0, 'height': 0}))
    display.preferences.fullscreen = True
    display.resized(SimpleNamespace(args={'width': 3840, 'height': 2160}))
    display.preferences.fullscreen = False
    display.maximized = True
    display.resized(SimpleNamespace(args={'width': 3840, 'height': 2160}))
    assert display.size == expected


def test_corrupt_display_file_does_not_block_startup(tmp_path):
    path = tmp_path / 'display.json'
    path.write_text('broken')
    assert DesktopDisplay(path).preferences == DisplayPreferences()


def test_failed_display_replace_keeps_existing_preferences(tmp_path):
    display = DesktopDisplay(tmp_path / 'display.json')
    display.save()
    before = display.path.read_bytes()
    with patch('steam_client.display.os.replace', side_effect=OSError), pytest.raises(OSError):
        display.save()
    assert display.path.read_bytes() == before
    assert not list(tmp_path.glob('.display-*.tmp'))


def test_manual_backups_are_valid_and_not_pruned(tmp_path):
    store = AtomicSaveStore(tmp_path / 'chronicles.json')
    store.save([{'gold': 55}, {}, {}])
    manual = store.create_manual_backup()
    for value in range(15):
        store.save([{'gold': value}, {}, {}])
    assert store._read(manual) == [{'gold': 55}, {}, {}]
    assert len(list(store.backups.glob('chronicles-*.json'))) == 10


def test_corrupt_save_is_not_exported_as_good_manual_backup(tmp_path):
    store = AtomicSaveStore(tmp_path / 'chronicles.json')
    store.path.write_text('{}')
    with pytest.raises((ValueError, SaveRecoveryRequired)):
        store.create_manual_backup()
    assert not list(store.backups.glob('manual-*.json'))
