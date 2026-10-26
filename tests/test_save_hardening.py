import copy
import json
from unittest.mock import patch

import pytest

from steam_client.storage import AtomicSaveStore, SaveConflictError


def slots(gold=10):
    return [{'player': {'gold': gold}}, {}, {}]


def test_unchanged_save_does_not_replace_or_rotate(tmp_path):
    store = AtomicSaveStore(tmp_path / 'chronicles.json')
    store.save(slots())
    with patch('steam_client.storage.os.replace', side_effect=AssertionError('redundant write')):
        assert store.save(slots()) is False
    assert not list(store.backups.glob('chronicles-*.json'))


def test_external_replacement_is_not_overwritten(tmp_path):
    store = AtomicSaveStore(tmp_path / 'chronicles.json')
    store.save(slots())
    other = AtomicSaveStore(store.path)
    other.load()
    other.save(slots(20))
    with pytest.raises(SaveConflictError):
        store.save(slots(30))
    assert other.load() == slots(20)


def test_external_deletion_is_not_treated_as_new_profile(tmp_path):
    store = AtomicSaveStore(tmp_path / 'chronicles.json')
    store.save(slots())
    store.path.unlink()
    with pytest.raises(SaveConflictError):
        store.save(slots(30))


def test_legacy_upgrade_preserves_payload_and_original_backup(tmp_path):
    store = AtomicSaveStore(tmp_path / 'chronicles.json')
    original = {'format_version': 1, 'slots': slots(), 'checksum': store._checksum(slots())}
    store.path.write_text(json.dumps(original))
    before = copy.deepcopy(original)
    loaded = store.load()
    assert loaded == slots()
    store.save(loaded)
    assert json.loads(store.path.read_text())['format_version'] == 2
    assert any(json.loads(p.read_text()) == before for p in store.backups.glob('chronicles-*.json'))


@pytest.mark.parametrize('field,bad_value', [('inventory', {}), ('equipped', []), ('gold', -5)])
def test_invalid_economy_payload_refused_without_replacing_save(tmp_path, field, bad_value):
    store = AtomicSaveStore(tmp_path / 'chronicles.json')
    store.save(slots())
    invalid = slots()
    invalid[0]['player'][field] = bad_value
    with pytest.raises((TypeError, ValueError)):
        store.save(invalid)
    assert store.load() == slots()


def test_recovery_reports_backup_and_preserves_bad_primary(tmp_path):
    store = AtomicSaveStore(tmp_path / 'chronicles.json')
    store.save(slots())
    store.save(slots(20))
    store.path.write_text('invalid')
    assert store.load() == slots()
    assert store.recovery_source is not None
    assert store.path.read_text() == 'invalid'
