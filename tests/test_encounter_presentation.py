import copy
from pathlib import Path
from types import SimpleNamespace

from test_runtime_regressions import sample_item, state_for

from steam_client.experience import (
    MONSTER_SIGNATURES,
    arena_opponent,
    encounter_signal,
    monster_signature,
)
from steam_client.experience_ui import last_find_html

ROOT = Path(__file__).resolve().parents[1]


def test_last_find_is_a_read_only_snapshot_through_a_new_battle(game):
    state = state_for(game)
    item = sample_item(game)
    state.player.inventory = [item]
    state.remember_last_monster_drop(item, 'well')
    original = state.last_monster_drop_item.to_dict()
    state.player.inventory.clear()
    state.fight_in_progress = True
    before = state.player.to_dict()
    markup = last_find_html(state, game)
    assert 'Inspect last dropped item' in markup and 'Well of Evil' in markup
    assert 'read-only record' in markup.lower() and 'disabled' not in markup
    assert state.last_monster_drop_item.to_dict() == original
    assert state.last_monster_drop_item is not item
    assert state.player.to_dict() == before and not state.player.inventory


def test_last_find_updates_only_with_a_real_drop_and_clears_for_a_new_run(game):
    state = state_for(game)
    assert 'No find yet' in last_find_html(state, game)
    a = sample_item(game)
    a.name = '<unsafe name>'
    state.remember_last_monster_drop(a)
    assert '&lt;unsafe name&gt;' in last_find_html(state, game)
    b = copy.deepcopy(a)
    b.name = 'New drop'
    state.remember_last_monster_drop(b, 'labyrinth')
    assert 'New drop' in last_find_html(state, game) and state.last_monster_drop_sequence == 2
    state.clear_last_monster_drop()
    assert 'No find yet' in last_find_html(state, game)


def test_encounter_metadata_ignores_hp_rounds_page_turn_and_receipt_serial(game):
    state = state_for(game)
    monster = game.generate_monster(45)[0]
    state.fight_in_progress = True
    first = encounter_signal(state, monster)
    before = monster.to_dict() if hasattr(monster, 'to_dict') else vars(monster).copy()
    state._experience_serial = 50
    state.monster_page_turn_active = True
    state.monster_page_turn_progress = .54
    state.player.hp -= 1
    assert encounter_signal(state, monster) == first
    assert (monster.to_dict() if hasattr(monster, 'to_dict') else vars(monster).copy()) == before
    state.fight_in_progress = False
    state.last_fight_outcome = 'victory'
    assert encounter_signal(state, monster)['phase'] == 'victory'
    state.active_slot_index = 1
    assert encounter_signal(state, monster)['p'] != first['p']


def test_all_existing_species_have_deterministic_non_stat_signatures(game):
    textures = {'veil', 'thorn', 'iron', 'ember', 'prism', 'tide'}
    for entry in game.MONSTER_ARCHETYPES:
        name = entry['type']
        assert name in MONSTER_SIGNATURES
        motif, texture = monster_signature(name + ' Lv 45')
        assert motif and texture in textures
        assert monster_signature(name) == (motif, texture)
    assert monster_signature('unknown')[0] == 'Shadowed presence'
    assert monster_signature('Moonfang Stalker') != monster_signature('Spell Eater')


def test_transition_engine_has_no_polling_network_or_gameplay_calls():
    source = (ROOT / 'steam_client/static/encounters.js').read_text()
    for forbidden in ('setInterval', 'setTimeout', 'requestAnimationFrame', 'fetch(', '.emit(', 'WebSocket(', '.click('):
        assert forbidden not in source
    assert 'animation.currentTime' in source and 'attributeFilter' in source
    assert 'prefers-reduced-motion' in source and 'mqReducedMotion' in source
    assert "window.addEventListener('blur'" in source


def test_unknown_monster_signal_can_render_without_an_opponent(game):
    state = state_for(game)
    state.last_fight_outcome = 'idle'
    assert encounter_signal(state, None)['e'] == ''
    state.player = SimpleNamespace(name='Hero', player_class='Black Guard')
    state.accessibility_reduce_motion = True
    assert encounter_signal(state, None)['reduced']


def test_arrival_never_uses_previous_monster_during_legacy_page_turn(game):
    state = state_for(game)
    state.page_turn_previous_monster = game.generate_monster(44)[0]
    state.current_monster = game.generate_monster(45)[0]
    state.monster_page_turn_active = True
    state.fight_in_progress = True
    signals = []
    for progress in (0, .22, .54, .82, 1):
        state.monster_page_turn_progress = progress
        assert arena_opponent(state) is state.current_monster
        signals.append(encounter_signal(state, arena_opponent(state)))
    assert all(signal == signals[0] for signal in signals)


def test_settle_end_pose_matches_static_css_after_animation_cleanup():
    css = (ROOT / 'steam_client/static/experience.css').read_text()
    script = (ROOT / 'steam_client/static/encounters.js').read_text()
    assert "transform:'scale(.985)'" in script
    for marker in ('[data-pd-phase="fled"] .pd-enemy-art', '[data-pd-phase="defeat"] .pd-hero-art'):
        rule = css.split(marker, 1)[1].split('}', 1)[0]
        assert 'transform:scale(.985)' in rule
