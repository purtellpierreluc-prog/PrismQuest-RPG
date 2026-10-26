import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare_steampipe', ROOT / 'tools' / 'prepare_steampipe.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


@pytest.mark.parametrize('bad', ['480', '-1', '0', 'abc', '12"\nSetLive', '1.5'])
def test_steam_configuration_refuses_missing_example_or_injected_ids(bad):
    with pytest.raises(ValueError):
        tool.render(bad, '123456', ROOT / 'dist', ROOT / 'build')


def test_steam_configuration_is_always_preview_and_never_sets_live():
    app, depot = tool.render('123456', '123457', ROOT / 'dist', ROOT / 'build')
    assert '"Preview" "1"' in app
    assert 'SetLive' not in app
    assert 'password' not in app.lower() and 'login' not in app.lower()
    assert 'steam_appid.txt' in depot
    assert depot.startswith('"DepotBuild"')


def test_steam_configuration_refuses_path_injection():
    with pytest.raises(ValueError):
        tool.render('123456', '123457', 'x"\nSetLive', ROOT / 'build')


def test_release_inventory_keeps_rights_unapproved_and_copies_real_license(tmp_path):
    from email.message import Message
    from importlib.metadata import PackagePath
    from types import SimpleNamespace

    from tools.release_audit import generate
    source = tmp_path / 'package'
    source.mkdir()
    (source / 'LICENSE').write_text('Test license fixture')
    metadata = Message()
    metadata['Name'], metadata['License-Expression'] = 'Fixture', 'MIT'
    distribution = SimpleNamespace(metadata=metadata, version='1', files=[PackagePath('LICENSE')], locate_file=lambda name: source / name)
    assets = tmp_path / 'assets'
    assets.mkdir()
    (assets / 'art.webp').write_bytes(b'fixture')
    report = generate(tmp_path / 'output', assets, [distribution])
    assert report['release_approved'] is False and report['asset_count'] == 1
    assert report['packages'][0]['review_required'] is False
    assert (tmp_path / 'output/third-party/licenses/Fixture/LICENSE').read_text() == 'Test license fixture'
    assert 'UNREVIEWED' in (tmp_path / 'output/asset-rights-review.csv').read_text()
