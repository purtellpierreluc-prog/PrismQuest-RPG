from pathlib import Path

from steam_client.paths import DesktopPaths
from steam_client.visuals import scene_heading

ROOT = Path(__file__).resolve().parents[1]


def test_scene_identity_escapes_character_strings():
    rendered = scene_heading('arena', '<script>bad()</script>', 45, 'Core')
    assert '<script>' not in rendered
    assert 'The Arena' in rendered and 'LV 45' in rendered
    assert 'aria-hidden="true"' in rendered


def test_visual_fork_has_local_fonts_with_license_notices():
    fonts = ROOT / 'steam_client/static/fonts'
    for name in ['Cinzel.ttf', 'Barlow-Regular.ttf', 'Barlow-SemiBold.ttf']:
        assert (fonts / name).stat().st_size > 10000
    for name in ['Cinzel-OFL.txt', 'Barlow-OFL.txt']:
        assert 'SIL OPEN FONT LICENSE' in (fonts / name).read_text()


def test_visual_layer_avoids_network_fonts_and_preserves_reduced_motion():
    source = (ROOT / 'steam_client/static/nocturne.css').read_text()
    assert '@import' not in source and 'https://' not in source
    assert '/desktop-ui/fonts/' in source
    assert 'prefers-reduced-motion' in source
    assert 'backdrop-filter: none' in source


def test_visual_fork_default_profile_cannot_overwrite_preserved_edition(tmp_path, monkeypatch):
    monkeypatch.delenv('PRISMQUEST_DATA_DIR', raising=False)
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.setattr('steam_client.paths.sys.platform', 'win32')
    assert DesktopPaths.from_environment().data == tmp_path / 'PrismQuest' / 'SteamEditionReimagined'


def test_local_fonts_are_included_in_package_inventory(tmp_path):
    from tools.release_audit import generate

    report = generate(tmp_path / 'release', ROOT / 'Assets', [])
    assert {font['name'] for font in report['bundled_fonts']} == {'Cinzel', 'Barlow'}
    for font in report['bundled_fonts']:
        assert (tmp_path / 'release' / font['license_file']).is_file()


def test_dynamic_game_import_has_explicit_packaging_dependency():
    spec = (ROOT / 'PrismQuestDesktop.spec').read_text()
    assert "'steam_client.visuals'" in spec
    assert "(str(root / 'steam_client' / 'static'), 'steam_client/static')" in spec
