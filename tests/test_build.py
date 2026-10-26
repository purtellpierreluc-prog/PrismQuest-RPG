import hashlib
import json
from pathlib import Path

from steam_client import __version__
from tools.build_manifest import build_manifest


def test_build_manifest_hashes_files_and_excludes_itself(tmp_path):
    (tmp_path / 'PrismQuest.exe').write_bytes(b'packaged-fixture')
    report = build_manifest(tmp_path)
    data = json.loads(report.read_text())
    assert data['version'] == __version__
    assert data['files_sha256'] == {'PrismQuest.exe': hashlib.sha256(b'packaged-fixture').hexdigest()}
    assert 'build-info.json' not in json.loads(build_manifest(tmp_path).read_text())['files_sha256']


def test_windows_version_matches_desktop_version():
    source = Path(__file__).resolve().parents[1] / 'steam_client' / 'windows_version.txt'
    assert f"StringStruct('ProductVersion', '{__version__}')" in source.read_text()


def test_windows_lock_covers_direct_runtime_requirements():
    root = Path(__file__).resolve().parents[1]
    lock = {line.casefold() for line in (root / 'requirements-windows-dev.lock.txt').read_text().splitlines()}
    for line in (root / 'requirements.txt').read_text().splitlines():
        if line and not line.startswith('#'):
            assert line.casefold() in lock
