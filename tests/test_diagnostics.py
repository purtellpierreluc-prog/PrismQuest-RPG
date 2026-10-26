import json
from unittest.mock import patch

import pytest

from steam_client.diagnostics import (
    collect_diagnostics,
    verify_package,
    write_diagnostics,
)
from steam_client.paths import DesktopPaths
from steam_client.storage import AtomicSaveStore


def test_diagnostics_does_not_export_names_items_secrets_or_absolute_paths(tmp_path):
    paths = DesktopPaths(tmp_path / 'resources', tmp_path / 'private-user-name')
    paths.prepare()
    store = AtomicSaveStore(paths.save_file)
    store.save([{'player': {'name': 'Private Hero', 'gold': 123}}, {}, {}])
    result = collect_diagnostics(paths, store)
    encoded = json.dumps(result)
    assert 'Private Hero' not in encoded and str(tmp_path) not in encoded
    assert '123' not in encoded
    assert result['saves']['occupied_slots'] == 1
    target = write_diagnostics(paths, store)
    assert json.loads(target.read_text())['product'] == 'PrismQuest'


def test_corrupt_save_diagnostics_does_not_repair_or_delete_it(tmp_path):
    paths = DesktopPaths(tmp_path, tmp_path / 'profile')
    paths.prepare()
    paths.save_file.write_text('corrupted private data')
    report = collect_diagnostics(paths)
    assert report['saves']['status'] == 'SaveRecoveryRequired'
    assert paths.save_file.read_text() == 'corrupted private data'


def test_manifest_rejects_path_traversal_and_modified_files(tmp_path):
    (tmp_path / 'PrismQuest.exe').write_bytes(b'exe')
    (tmp_path / 'build-info.json').write_text(json.dumps({'files_sha256': {'../secret': 'abc'}}))
    with pytest.raises(ValueError, match='path'):
        verify_package(tmp_path)
    (tmp_path / 'build-info.json').write_text(json.dumps({'files_sha256': {'PrismQuest.exe': 'bad'}}))
    assert verify_package(tmp_path)['valid'] is False


def test_missing_webview_detected_without_launching_or_downloading(tmp_path):
    from steam_client.diagnostics import check_native_prerequisites
    with patch('steam_client.diagnostics.sys.platform', 'win32'), patch('steam_client.diagnostics.webview_version', return_value=None), pytest.raises(RuntimeError, match='WebView2'):
        check_native_prerequisites()
