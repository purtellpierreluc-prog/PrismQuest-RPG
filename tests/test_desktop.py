import copy
import json
from unittest.mock import patch

import pytest
from test_runtime_regressions import sample_item, start_encounter, state_for

from steam_client.paths import DesktopPaths
from steam_client.storage import (
    AtomicSaveStore,
    SaveRecoveryRequired,
    SingleInstance,
    UnsupportedSaveVersion,
)


def slots(gold=0):
    return [{'player': {'gold': gold}}, {}, {}]


def test_local_paths_are_separate_from_game_installation(tmp_path, monkeypatch):
    monkeypatch.setenv('PRISMQUEST_DATA_DIR', str(tmp_path / 'profile'))
    paths = DesktopPaths.from_environment()
    paths.prepare()
    assert paths.save_file.parent == tmp_path / 'profile' / 'saves'
    assert paths.resources != paths.data
    assert paths.cache.is_dir() and paths.backups.is_dir()


def test_atomic_save_round_trip(tmp_path):
    store = AtomicSaveStore(tmp_path / 'chronicles.json')
    assert store.load() is None
    store.save(slots(25))
    assert store.load() == slots(25)
    assert json.loads(store.path.read_text())['format_version'] == 1


def test_corrupt_primary_recovers_backup_without_destroying_it(tmp_path):
    store = AtomicSaveStore(tmp_path / 'chronicles.json')
    store.save(slots(25))
    store.save(slots(50))
    store.path.write_text('{interrupted write')
    assert store.load() == slots(25)
    store.save(slots(75))
    assert store.load() == slots(75)
    assert list(store.backups.glob('unreadable-*.json'))
    assert any(json.loads(path.read_text())['slots'] == slots(25) for path in store.backups.glob('chronicles-*.json'))


def test_corrupt_save_without_backup_fails_instead_of_resetting_progress(tmp_path):
    store = AtomicSaveStore(tmp_path / 'chronicles.json')
    store.path.write_text('broken')
    with pytest.raises(SaveRecoveryRequired):
        store.load()
    assert store.path.read_text() == 'broken'


def test_checksum_detects_partial_or_modified_save(tmp_path):
    store = AtomicSaveStore(tmp_path / 'chronicles.json')
    store.save(slots(25))
    payload = json.loads(store.path.read_text())
    payload['slots'][0]['player']['gold'] = 999
    store.path.write_text(json.dumps(payload))
    with pytest.raises(SaveRecoveryRequired):
        store.load()


def test_failed_replace_preserves_original_and_cleans_temporary_file(tmp_path):
    store = AtomicSaveStore(tmp_path / 'chronicles.json')
    store.save(slots(25))
    with patch('steam_client.storage.os.replace', side_effect=OSError('disk unavailable')), pytest.raises(OSError):
        store.save(slots(50))
    assert store.load() == slots(25)
    assert not list(tmp_path.glob('*.tmp'))


def test_legacy_local_save_can_be_read(tmp_path):
    store = AtomicSaveStore(tmp_path / 'chronicles.json')
    store.path.write_text(json.dumps({'slots': slots(25)}))
    assert store.load() == slots(25)


def test_backups_are_bounded(tmp_path):
    store = AtomicSaveStore(tmp_path / 'chronicles.json')
    for gold in range(15):
        store.save(slots(gold))
    assert len(list(store.backups.glob('chronicles-*.json'))) == 10
    assert store.load() == slots(14)


def test_newer_save_never_silently_downgrades_to_backup(tmp_path):
    store = AtomicSaveStore(tmp_path / 'chronicles.json')
    store.save(slots(25))
    store.save(slots(50))
    future = json.loads(store.path.read_text())
    future['format_version'] = 2
    store.path.write_text(json.dumps(future))
    with pytest.raises(UnsupportedSaveVersion):
        store.load()
    with pytest.raises(UnsupportedSaveVersion):
        store.save(slots(75))
    assert json.loads(store.path.read_text()) == future


def test_game_slot_persistence_uses_desktop_store(game, tmp_path, monkeypatch):
    monkeypatch.setattr(game, 'DESKTOP_SAVE_STORE', AtomicSaveStore(tmp_path / 'chronicles.json'))
    payload = [game.build_default_slot_payload() for _ in range(3)]
    payload[0]['player'] = game.create_player('Black Guard').to_dict()
    payload[0]['player']['gold'] = 135
    game.persist_slots(payload)
    assert game.load_persisted_slots()[0]['player']['gold'] == 135


def test_startup_error_preserves_files_and_writes_diagnostics(tmp_path, monkeypatch):
    from steam_client.runtime import report_startup_error
    monkeypatch.setenv('PRISMQUEST_DATA_DIR', str(tmp_path))
    monkeypatch.setattr('sys.argv', ['launch_desktop.py', '--browser'])
    store = AtomicSaveStore(tmp_path / 'saves' / 'chronicles.json')
    store.save(slots(25))
    report_startup_error(SaveRecoveryRequired('Unreadable save'))
    assert store.load() == slots(25)
    assert 'Unreadable save' in (tmp_path / 'logs' / 'startup-error.log').read_text()


def test_desktop_runtime_is_offline_and_loopback_only(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from nicegui import app, ui

    from steam_client import runtime
    monkeypatch.setenv('SUPABASE_URL', 'https://production.invalid')
    monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY', 'do-not-inherit')
    monkeypatch.setenv('PRISMQUEST_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('PRISMQUEST_DESKTOP', '0')
    monkeypatch.setenv('NICEGUI_STORAGE_PATH', str(tmp_path / 'ui'))
    monkeypatch.setattr(runtime, 'load_game', lambda _paths: SimpleNamespace(flush_desktop_save=lambda: None))
    monkeypatch.setattr(app, 'on_shutdown', lambda _callback: None)
    run = patch.object(ui, 'run')
    with run as mocked:
        runtime.launch(['--browser', '--port', '8097', '--data-dir', str(tmp_path)])
    assert mocked.call_args.kwargs['host'] == '127.0.0.1'
    assert mocked.call_args.kwargs['native'] is False
    assert mocked.call_args.kwargs['reload'] is False
    assert runtime.os.environ['SUPABASE_URL'] == ''
    assert runtime.os.environ['SUPABASE_PUBLISHABLE_KEY'] == ''
    assert runtime.os.environ['PRISMQUEST_DATA_DIR'] == str(tmp_path.resolve())


def test_second_instance_cannot_share_local_save_profile(tmp_path):
    first = SingleInstance(tmp_path / 'game.lock').acquire()
    try:
        with pytest.raises(RuntimeError, match='already running'):
            SingleInstance(tmp_path / 'game.lock').acquire()
    finally:
        first.release()
    second = SingleInstance(tmp_path / 'game.lock').acquire()
    second.release()


def test_desktop_return_to_title_then_play_keeps_character(game, monkeypatch):
    monkeypatch.setattr(game, 'DESKTOP_MODE', True)
    state = state_for(game)
    expected = state.player.to_dict()
    state.return_to_title()
    assert state.active_slot_index is None
    state.go_to_chronicles()
    assert state.slots[0]['player'] == expected
    state.open_slot(0)
    assert state.player.to_dict() == expected


def test_desktop_lab_round_resumes_from_disk_checkpoint(game, monkeypatch):
    monkeypatch.setattr(game, 'DESKTOP_MODE', True)
    state = state_for(game)
    start_encounter(game, state)
    assert state.run_labyrinth_encounter(ignore_timing=True)
    state.sync_active_slot()
    expected_run = copy.deepcopy(state.labyrinth_session_row)
    expected_player = state.player.to_dict()
    reloaded = state_for(game)
    reloaded.slots = copy.deepcopy(state.slots)
    reloaded.open_slot(0)
    assert reloaded.labyrinth_is_local
    assert reloaded.labyrinth_session_row['pending_encounter']['round'] == expected_run['pending_encounter']['round']
    assert reloaded.player.to_dict() == expected_player
    assert reloaded.screen == 'game' and reloaded.game_tab == 'labyrinth'


def test_explicit_leave_clears_checkpoint(game, monkeypatch):
    monkeypatch.setattr(game, 'DESKTOP_MODE', True)
    state = state_for(game)
    start_encounter(game, state)
    state.sync_active_slot()
    assert state.slots[0]['desktop_labyrinth_run']
    state.leave_labyrinth_session()
    assert not state.slots[0]['desktop_labyrinth_run']


def test_lab_checkpoint_round_trip_serializes_item_views_and_companions(game, monkeypatch, tmp_path):
    monkeypatch.setattr(game, 'DESKTOP_MODE', True)
    state = state_for(game)
    state.player.inventory = [sample_item(game)]
    assert state.create_labyrinth_solo_session()
    assert state.labyrinth_hire_companion('Shadow Mage')
    assert state.labyrinth_start_floor()
    state.sync_active_slot()
    before = state.player.to_dict()
    store = AtomicSaveStore(tmp_path / 'chronicles.json')
    store.save(state.slots)
    reloaded = state_for(game)
    reloaded.slots = store.load()
    reloaded.open_slot(0)
    assert reloaded.player.to_dict() == before
    assert len(reloaded.labyrinth_member_rows) == 2
    assert len(reloaded.player.inventory) == 1
    assert isinstance(reloaded.labyrinth_member_rows[0]['profile_snapshot']['inventory_items'][0], game.Item)


def test_lab_member_normalization_preserves_empty_resources(game):
    row = game._labyrinth_normalize_member_row({'max_hp': 5000, 'current_hp': 0, 'max_mana': 2000, 'current_mana': 0, 'is_downed': True})
    assert row['current_hp'] == 0 and row['current_mana'] == 0 and row['is_downed']


def test_desktop_refuses_online_only_scenes(game, monkeypatch):
    monkeypatch.setattr(game, 'DESKTOP_MODE', True)
    state = state_for(game)
    state.screen = 'town'
    state.game_tab = 'arena'
    for tab in ('bazaar', 'guild_hall', 'donate'):
        state.open_game_tab(tab)
        assert state.screen == 'town' and state.game_tab == 'arena'
    state.guided_discord_prompt_seen = True
    state.open_game_tab('ladder')
    assert state.screen == 'game' and state.game_tab == 'ladder'
    assert state.scene_tutorial_open_key == ''
