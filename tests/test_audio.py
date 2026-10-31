import array
import copy
import hashlib
import json
import math
import sys
import wave
from pathlib import Path
from unittest.mock import patch

import pytest
from test_runtime_regressions import sample_item, state_for

from steam_client.audio import AudioPreferences, DesktopAudio, audio_signal

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('payload', [None, [], 'bad'])
def test_missing_audio_preferences_are_quiet(payload):
    prefs = AudioPreferences.from_payload(payload)
    assert prefs == AudioPreferences()
    assert prefs.music_volume < prefs.effects_volume < 50
    assert prefs.mute_unfocused


def test_audio_preference_validation():
    prefs = AudioPreferences.from_payload({'effects_volume': 500, 'music_volume': -20, 'muted': 'false',
                                            'combat_enabled': False, 'music_enabled': 'yes'})
    assert prefs.effects_volume == 100 and prefs.music_volume == 0
    assert not prefs.muted and not prefs.combat_enabled and prefs.music_enabled
    for value in (float('inf'), None, 'bad', True, float('nan')):
        assert AudioPreferences.from_payload({'music_volume': value}).music_volume == 18


def test_audio_settings_do_not_write_character_saves(tmp_path):
    path = tmp_path / 'audio.json'
    settings = DesktopAudio(path)
    settings.set('music_volume', 12)
    settings.set('muted', True)
    settings.flush()
    reloaded = DesktopAudio(path)
    assert reloaded.preferences.music_volume == 12 and reloaded.preferences.muted
    assert sorted(p.name for p in tmp_path.iterdir()) == ['audio.json']


def test_audio_preference_failed_replace_preserves_file(tmp_path):
    settings = DesktopAudio(tmp_path / 'audio.json')
    settings.save()
    original = settings.path.read_bytes()
    with patch('steam_client.audio.os.replace', side_effect=OSError), pytest.raises(OSError):
        settings.save()
    assert settings.path.read_bytes() == original
    assert not list(tmp_path.glob('.audio-*.tmp'))


def test_corrupt_audio_preferences_do_not_block_startup(tmp_path):
    path = tmp_path / 'audio.json'
    path.write_text('broken')
    settings = DesktopAudio(path)
    assert settings.preferences == AudioPreferences()
    assert path.read_text() == 'broken'


def test_audio_reset_and_unknown_keys(tmp_path):
    settings = DesktopAudio(tmp_path / 'audio.json')
    settings.set('effects_volume', 0)
    settings.reset()
    assert settings.preferences == AudioPreferences()
    with pytest.raises(ValueError):
        settings.set('player_gold', 0)


def test_audio_signal_reads_only_presentation_and_uses_latest_hit(game):
    state = state_for(game)
    state.game_tab = 'arena'
    state.last_monster_drop_item = sample_item(game)
    state.last_monster_drop_sequence = 4
    state.player_damage_popup_at, state.monster_damage_popup_at = 10, 20
    state.player_damage_popup_crit, state.monster_damage_popup_crit = True, False
    before = copy.deepcopy(state.player.to_dict())
    first = audio_signal(state)
    assert first == audio_signal(state)
    assert first['q'] == 'Rare' and first['r'] == 4 and not first['c']
    assert state.player.to_dict() == before
    state.screen = 'title'
    assert audio_signal(state)['p'] == ''


def test_lab_audio_detects_combat_without_arena_fight_flag(game):
    state = state_for(game, player_class='Warlock')
    state.fight_in_progress = False
    state.labyrinth_session_row = {'id': 'local', 'floor': 1, 'status': 'boss', 'pending_encounter': {'started_at': 'test'}}
    signal = audio_signal(state)
    assert signal['a'] and signal['k'] == 'spell'
    assert signal['e'] == 'lab:local:1:test'
    state.labyrinth_session_row['status'] = 'reward'
    assert audio_signal(state)['o'] == 'victory'


def test_bundled_audio_is_original_bounded_and_has_seamless_loops():
    folder = ROOT / 'steam_client/static/audio/v1'
    manifest = json.loads((folder / 'manifest.json').read_text())
    assert 'no external' in manifest['origin']
    assert len(manifest['files']) == 11
    for name, info in manifest['files'].items():
        path = folder / f'{name}.wav'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == info['sha256']
        with wave.open(str(path)) as stream:
            assert stream.getnchannels() == 1 and stream.getsampwidth() == 2
            assert stream.getframerate() == 22050
            samples = array.array('h', stream.readframes(stream.getnframes()))
        if sys.byteorder != 'little':
            samples.byteswap()
        assert max(abs(value) for value in samples) < 32767 * .8
        assert math.isclose(info['seconds'], len(samples)/22050)
        assert abs(sum(samples)/len(samples)) < 1
        if name in {'ambient', 'undertone'}:
            assert abs(samples[-1]-samples[0]) < 500
        else:
            assert abs(samples[0]) < 100 and abs(samples[-1]) < 150


def test_audio_engine_is_local_event_driven_and_packaged():
    source = (ROOT / 'steam_client/static/audio.js').read_text()
    assert 'setInterval' not in source and 'requestAnimationFrame' not in source
    assert 'https://' not in source and '/desktop-ui/audio/v1/' in source
    assert 'visibilitychange' in source and "window.addEventListener('blur'" in source
    assert '750' in source and 'seen.size > 128' in source
    assert "'steam_client.audio'" in (ROOT / 'PrismQuestDesktop.spec').read_text()


@pytest.mark.parametrize('version,count', [(2,8),(3,4)])
def test_chapter_score_is_original_quiet_and_seamless(version, count):
    folder = ROOT / f'steam_client/static/audio/v{version}'
    manifest = json.loads((folder / 'manifest.json').read_text())
    assert manifest['version'] == version and 'no external' in manifest['origin']
    assert len(manifest['files']) == count
    for name, info in manifest['files'].items():
        path = folder / f'{name}.wav'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == info['sha256']
        with wave.open(str(path)) as stream:
            assert stream.getnchannels() == 1 and stream.getsampwidth() == 2
            assert stream.getframerate() == 22050
            samples = array.array('h', stream.readframes(stream.getnframes()))
        if sys.byteorder != 'little':
            samples.byteswap()
        assert max(abs(value) for value in samples) < 32767 * .22
        assert math.isclose(info['seconds'], len(samples)/22050)
        assert abs(sum(samples)/len(samples)) < 2
        if name == 'prism_bed':
            assert abs(samples[-1]-samples[0]) < 100
        else:
            assert abs(samples[0]) < 100 and abs(samples[-1]) < 150


def test_chapter_effects_are_finite_and_do_not_expose_answers():
    source = (ROOT / 'steam_client/static/chapters.js').read_text()
    assert 'setInterval' not in source and 'requestAnimationFrame' not in source
    assert 'solution' not in source and 'Infinity' not in source
    assert 'prefers-reduced-motion' in source and 'visibilitychange' in source
    engine = (ROOT / 'steam_client/static/audio.js').read_text()
    assert 'ticket !== chapterTicket' in engine
    assert 'scoreMode' in engine and '/desktop-ui/audio/v2/' in engine
    assert 'if (!old || old.p !== signal.p) stopVoices();' in engine
