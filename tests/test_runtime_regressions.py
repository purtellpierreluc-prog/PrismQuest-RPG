"""Offline regression tests. No credentials, live saves, or database writes are used."""

import ast
import asyncio
import copy
import os
import random
import sys
import time
import types
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'Deploy' / 'PrismQuest_RPG_v1.01.py'
if not SOURCE.exists():
    SOURCE = ROOT / 'PrismQuest_RPG_v1.01.py'


@pytest.fixture(scope='session')
def game(tmp_path_factory):
    tree = ast.parse(SOURCE.read_text(encoding='utf-8-sig'))
    kept = []
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and ast.unparse(node.value.func).startswith('ui.'):
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node.decorator_list = [d for d in node.decorator_list if not ast.unparse(d).startswith(('ui.', 'app.'))]
        if isinstance(node, ast.Try) and 'os.chdir' in ast.unparse(node):
            continue
        kept.append(node)
    tree.body = kept
    module = types.ModuleType('prismquest_offline_tests')
    module.__file__ = str(tmp_path_factory.mktemp('game') / 'game.py')
    sys.modules[module.__name__] = module
    with patch.dict(os.environ, {'SUPABASE_URL': '', 'SUPABASE_PUBLISHABLE_KEY': ''}):
        exec(compile(tree, str(SOURCE), 'exec'), module.__dict__)  # noqa: S102 - trusted repository source, UI startup removed for tests
    return module


def state_for(game, player_class='Black Guard', level=45):
    state = game.SessionState()
    state.persist_runtime_session = Mock()
    state.persist_to_disk = Mock()
    state.supabase = None
    state.slots = [game.build_default_slot_payload() for _ in range(3)]
    state.active_slot_index = 0
    state.player = game.create_player(player_class)
    while state.player.level < level:
        game.gain_xp(state.player, state.player.xp_to_next - state.player.xp, None)
    state.player.gold = 10000
    state.screen = 'game'
    state.game_tab = 'labyrinth'
    state.guided_intro_stage = game.GUIDED_INTRO_COMPLETE
    return state


def sample_item(game, name='Audit Axe'):
    return game.Item(name, 'weapon', 45, 'Rare', 'Axe', {'attack_damage_min': 40, 'attack_damage_max': 65}, {'strength': 15})


def start_encounter(game, state, *, boss=False):
    assert state.create_labyrinth_solo_session()
    assert state.labyrinth_start_floor()
    row = dict(state.labyrinth_session_row)
    row['status'] = 'boss' if boss else 'encounter'
    row['pending_encounter'] = game._labyrinth_build_shared_encounter(
        state, row, state.labyrinth_member_rows, game._labyrinth_choose_template(boss),
        state.player.level, boss=boss, tile_key='0,0',
    )
    game._labyrinth_apply_local_session_update(state, row)
    return state.labyrinth_session_row['pending_encounter']


@pytest.mark.parametrize('player_class', ['Black Guard', 'Warlock', 'Ember Fae', 'Prismatic Templar'])
def test_player_serialization_matches_dataclass_and_is_independent(game, player_class):
    player = game.create_player(player_class)
    player.inventory = [sample_item(game, str(i)) for i in range(120)]
    payload = player.to_dict()
    assert payload == asdict(player)
    restored = game.Player.from_dict(payload)
    restored.inventory[0].affix_stats['strength'] = 999
    payload['equipped']['weapon']['affix_stats']['strength'] = 888
    assert player.inventory[0].affix_stats['strength'] == 15
    assert player.equipped['weapon'].affix_stats.get('strength') != 888


def test_item_load_does_not_share_stats_with_saved_payload(game):
    payload = sample_item(game).to_dict()
    restored = game.Item.from_dict(payload)
    restored.affix_stats['strength'] = 999
    assert payload['affix_stats']['strength'] == 15


@pytest.mark.parametrize('raw, expected', [(0, 0), ('0', 0), (None, -1), ('bad', -1), (2, 2)])
def test_first_selection_remains_selectable(game, raw, expected):
    assert game.selection_index(raw) == expected


def test_first_prism_vote_is_counted_and_remembered(game):
    state = state_for(game)
    state.labyrinth_is_local = True
    member_id = game._labyrinth_member_identity(state)
    state.labyrinth_session_row = {'id': 'vote-test', 'floor': 1}
    state.labyrinth_vote_rows = [{'user_id': member_id, 'floor': 1, 'choice_index': 0}]
    assert game._labyrinth_vote_count_map(state.labyrinth_vote_rows) == {0: 1}
    assert game.labyrinth_current_vote_choice(state) == 0


def test_lab_zero_health_and_mana_stay_zero(game):
    player = game.create_player('Shadow Mage')
    entry = {'player_snapshot': player.to_dict(), 'current_hp': 0, 'current_mana': 0}
    restored = game._labyrinth_member_player_from_entry(entry, {})
    assert restored.hp == 0
    assert restored.mana == 0


def test_lab_combat_snapshot_keeps_independent_inventory(game):
    player = game.create_player('Black Guard')
    player.inventory = [sample_item(game)]
    raw = player.to_dict()
    entry = {'player_snapshot': raw, 'current_hp': player.hp, 'current_mana': player.mana}
    fighter = game._labyrinth_member_player_from_entry(entry, {})
    fighter.inventory[0].affix_stats['strength'] = 22
    updated = game._labyrinth_store_entry_from_player(entry, fighter)
    fighter.inventory[0].affix_stats['strength'] = 33
    assert updated['player_snapshot']['inventory'][0]['affix_stats']['strength'] == 22
    assert raw['inventory'][0]['affix_stats']['strength'] == 15


def test_unchanged_lab_snapshot_does_not_rebuild_or_save(game):
    state = state_for(game)
    start_encounter(game, state)
    state.sync_active_slot = Mock()
    state.labyrinth_last_self_snapshot_key = None
    assert game._labyrinth_sync_self_from_party_state(state, state.labyrinth_session_row)
    old_player = state.player
    saves = state.sync_active_slot.call_count
    assert not game._labyrinth_sync_self_from_party_state(state, state.labyrinth_session_row)
    assert state.player is old_player
    assert state.sync_active_slot.call_count == saves


def test_repair_does_not_reconstruct_valid_party(game):
    state = state_for(game)
    start_encounter(game, state)
    with patch.object(game, '_labyrinth_party_state_for_session', side_effect=AssertionError('unnecessary reconstruction')):
        game._labyrinth_repair_session_row(state, state.labyrinth_session_row, state.labyrinth_member_rows)


def test_local_commit_applies_companion_changes_once(game):
    state = state_for(game)
    start_encounter(game, state)
    state.sync_active_slot = Mock()
    state.labyrinth_last_slot_sync_at = 0
    row = copy.deepcopy(state.labyrinth_session_row)
    row['recent_events'].append('Companion progress changed')
    before = state.labyrinth_last_snapshot_hash
    assert game._labyrinth_upsert_session_row(state, row)
    assert state.labyrinth_last_snapshot_hash == before
    assert game._labyrinth_apply_local_session_update(state, row)
    assert state.sync_active_slot.call_count == 1


def test_stale_round_callback_does_not_advance_combat(game):
    state = state_for(game)
    pending = start_encounter(game, state)
    before = copy.deepcopy(state.labyrinth_session_row)
    key = (before['id'], pending['started_at'], pending['sequence'] - 1)
    assert not state.run_labyrinth_encounter(ignore_timing=True, expected_step=key)
    assert state.labyrinth_session_row == before
    assert not state.run_labyrinth_encounter(ignore_timing=False)


def test_solo_round_stays_consistent_with_saved_character(game):
    random.seed(1234)
    state = state_for(game)
    pending = start_encounter(game, state)
    previous_round = pending['round']
    assert state.run_labyrinth_encounter(ignore_timing=True)
    row = state.labyrinth_session_row
    entry = row['pending_encounter']['party_state'][game._labyrinth_member_identity(state)]
    assert state.player.hp == game.Player.from_dict(entry['player_snapshot']).hp
    game._labyrinth_maybe_sync_active_slot(state, force=True)
    assert state.slots[0]['player']['hp'] == state.player.hp
    if row['status'] == 'encounter':
        assert row['pending_encounter']['round'] == previous_round + 1
        assert row['pending_encounter']['turn_index'] == 0


def test_lab_preserves_inventory_through_combat_and_selling(game):
    random.seed(442)
    state = state_for(game)
    state.player.inventory = [sample_item(game, str(i)) for i in range(30)]
    start_encounter(game, state)
    state.sell_item(0)
    sold_name = '0'
    expected = state.player.to_dict()['inventory']
    assert state.run_labyrinth_encounter(ignore_timing=True)
    names = [item.name for item in state.player.inventory]
    assert sold_name not in names
    assert state.player.to_dict()['inventory'][:len(expected)] == expected


def test_boss_rewards_are_awarded_once_and_saved(game):
    state = state_for(game)
    pending = start_encounter(game, state, boss=True)
    for monster in pending['monster_snapshots']:
        monster.update(hp=1, physical_armor=0, magic_resistance=0, evasion=0)
    before_gold = state.player.gold
    before_items = len(state.player.inventory)
    with patch.object(game, 'hit_success', return_value=True):
        assert state.run_labyrinth_encounter(ignore_timing=True)
    assert state.labyrinth_session_row['status'] == 'reward'
    assert state.player.level == 46
    assert 100 <= state.player.gold - before_gold <= 150
    assert len(state.player.inventory) == before_items + 1
    saved = copy.deepcopy(state.slots[0]['player'])
    assert saved['gold'] == state.player.gold
    assert not state.run_labyrinth_encounter(ignore_timing=True)
    assert state.slots[0]['player'] == saved


def test_five_player_three_monster_round_keeps_turn_order(game):
    state = state_for(game)
    assert state.create_labyrinth_solo_session()
    for player_class in ['Black Guard', 'Night Angel', 'Warlock', 'Shadow Mage']:
        assert state.labyrinth_hire_companion(player_class)
    assert state.labyrinth_start_floor()
    row = dict(state.labyrinth_session_row)
    row['status'] = 'encounter'
    row['pending_encounter'] = game._labyrinth_build_shared_encounter(
        state, row, state.labyrinth_member_rows, game._labyrinth_choose_template(False),
        45, boss=False, tile_key='0,0',
    )
    for monster in row['pending_encounter']['monster_snapshots']:
        monster.update(hp=100000, max_hp=100000)
    for entry in row['pending_encounter']['party_state'].values():
        entry['player_snapshot']['base_max_hp'] = 100000
        entry['current_hp'] = 100000
    game._labyrinth_apply_local_session_update(state, row)
    order = []
    original = game._labyrinth_resolve_turn
    def record_turn(attacker, defender, context):
        order.append(context['attacker_key'])
        return original(attacker, defender, context)
    with patch.object(game, '_labyrinth_resolve_turn', side_effect=record_turn):
        assert state.run_labyrinth_encounter(ignore_timing=True)
    assert len(order) == 8
    assert order[:5] == row['pending_encounter']['participants']
    assert order[5:] == ['monster-0', 'monster-1', 'monster-2']


def test_vault_round_trip_keeps_item_ownership(game):
    state = state_for(game)
    item = sample_item(game)
    state.player.inventory = [item]
    state.vault_capacity = 10
    state.store_vault_item(0)
    assert not state.player.inventory and len(state.vault_items) == 1
    state.withdraw_vault_item(0)
    assert not state.vault_items and state.player.inventory[0].to_dict() == item.to_dict()
    state.sell_item(0)
    assert not state.player.inventory
    assert not state.slots[0]['player']['inventory']


def test_saved_set_round_trip_keeps_exactly_one_item(game):
    state = state_for(game)
    item = sample_item(game)
    state.player.inventory = [item]
    state.save_selected_item_to_set(0)
    category = game.get_saved_item_category(item)
    assert not state.player.inventory
    assert state.saved_item_sets[category][45].to_dict() == item.to_dict()
    state.retrieve_saved_item_to_inventory(category, 45)
    assert len(state.player.inventory) == 1
    assert 45 not in state.saved_item_sets[category]


@pytest.mark.parametrize('index', [0, '0'])
def test_roster_equipment_transfers_and_returns_first_item_once(game, index):
    state = state_for(game)
    assert state.create_labyrinth_solo_session()
    assert state.labyrinth_buy_roster_companion('Black Guard')
    roster_id = state.labyrinth_roster_companions[0]['id']
    item = sample_item(game)
    state.player.inventory = [item]
    assert state.labyrinth_set_roster_companion_item(roster_id, 'weapon', index)
    assert not state.player.inventory
    assert state.labyrinth_roster_companions[0]['equipped']['weapon'] == item.to_dict()
    assert state.labyrinth_clear_roster_companion_item(roster_id, 'weapon')
    assert len(state.player.inventory) == 1
    assert state.player.inventory[0].to_dict() == item.to_dict()
    assert not state.labyrinth_clear_roster_companion_item(roster_id, 'weapon')
    assert len(state.player.inventory) == 1


@pytest.mark.parametrize('player_class', ['Black Guard', 'Warlock', 'Night Angel', 'Prismatic Templar'])
def test_arena_combat_remains_functional(game, player_class):
    random.seed(77)
    player = game.create_player(player_class)
    monster, _ = game.generate_monster(1, forced_level=1, player_class=player_class)
    timeline = game.build_combat_timeline(player, monster)
    assert timeline
    assert not player.is_alive() or not monster.is_alive()
    assert 0 <= player.hp <= player.max_hp


def test_async_lab_poll_does_not_block_and_rejects_stale_reads(game):
    state = state_for(game)
    state.labyrinth_is_local = False
    state.labyrinth_session_id = 'remote-test'
    state.labyrinth_join_code = 'LUX-AUDIT'
    state.auth_user_id = 'audit-user'
    state.supabase = object()
    state.is_authenticated = lambda: True
    state.labyrinth_last_sync_at = 0
    state.labyrinth_snapshot_revision = 1

    def slow_read(*_args):
        time.sleep(0.08)
        return {}, [], []

    async def check():
        with patch.object(game, '_labyrinth_fetch_session_rows', side_effect=slow_read):
            task = asyncio.create_task(game.labyrinth_refresh_session_state_async(state))
            await asyncio.sleep(0.015)
            assert not task.done()
            state.labyrinth_snapshot_revision += 1
            assert not await task
            assert state.labyrinth_session_id == 'remote-test'
            assert not state.labyrinth_poll_in_flight
    asyncio.run(check())


def test_combat_deadline_retains_fractional_seconds(game):
    state = state_for(game)
    before = datetime.now(UTC)
    deadline = game._labyrinth_parse_iso_timestamp(game._labyrinth_next_step_iso(state, 1.5))
    assert timedelta(seconds=1.49) <= deadline - before < timedelta(seconds=1.6)
