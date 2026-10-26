import copy
import random
from collections import Counter

import pytest
from test_runtime_regressions import sample_item, state_for

from steam_client.storage import AtomicSaveStore


def inventory_counts(state):
    items = list(state.player.inventory) + list(state.vault_items)
    items += [item for item in state.player.equipped.values() if item]
    items += [item for category in state.saved_item_sets.values() for item in category.values()]
    return Counter(str(sorted(item.to_dict().items())) for item in items)


def test_randomized_item_moves_and_disk_reloads_conserve_ownership(game, monkeypatch, tmp_path):
    monkeypatch.setattr(game, 'DESKTOP_MODE', True)
    rng = random.Random(20261026)
    state = state_for(game)
    state.player.inventory = [sample_item(game, f'Item {index // 2}') for index in range(40)]
    state.vault_capacity = 60
    expected = inventory_counts(state)
    store = AtomicSaveStore(tmp_path / 'chronicles.json')
    for step in range(240):
        choice = rng.randrange(6)
        if choice == 0 and state.player.inventory:
            state.store_vault_item(rng.randrange(len(state.player.inventory)))
        elif choice == 1 and state.vault_items:
            state.withdraw_vault_item(rng.randrange(len(state.vault_items)))
        elif choice == 2 and state.player.inventory:
            state.save_selected_item_to_set(rng.randrange(len(state.player.inventory)))
        elif choice == 3:
            pairs = [(category, tier) for category, items in state.saved_item_sets.items() for tier in items]
            if pairs:
                state.retrieve_saved_item_to_inventory(*rng.choice(pairs))
        elif choice == 4 and state.player.inventory:
            state.equip_item(rng.randrange(len(state.player.inventory)))
        else:
            state.unequip_slot('weapon')
        assert inventory_counts(state) == expected, step
        if step % 20 == 0:
            state.sync_active_slot()
            store.save(state.slots)
            reloaded = state_for(game)
            reloaded.slots = store.load()
            reloaded.open_slot(0)
            state = reloaded
            assert inventory_counts(state) == expected, ('reload', step)


def test_final_desktop_prestige_preserves_all_chronicles_and_current_equipment(game, monkeypatch):
    monkeypatch.setattr(game, 'DESKTOP_MODE', True)
    state = state_for(game, 'Prismatic Sorceress', 60)
    state.player.inventory = [sample_item(game)]
    state.slots[1]['player'] = game.create_player('Shadow Mage').to_dict()
    state.slots[2]['player'] = game.create_player('Black Guard').to_dict()
    state.sync_active_slot()
    before_others = copy.deepcopy(state.slots[1:])
    before_items = inventory_counts(state)
    state.finish_masterquest_attempt(True)
    assert state.slots[1:] == before_others
    assert state.player is not None and state.player.level == 60
    assert inventory_counts(state) == before_items
    assert state.slots[0]['pq_ledger_entries'][0]['passed'] is True


@pytest.mark.parametrize('player_class', [
    'Black Guard', 'Shadow Mage', 'Jade Samurai', 'Solaris Paladin', 'Monk of Selune',
    'Night Assassin', 'Warlock', 'Chroma Reaver', 'Prismatic Sorceress', 'Shadow Warrior',
    'Night Angel', 'Frost Oracle', 'Alecloak Thief', 'Shadow Arcanist', 'Executioner',
    'Ember Fae', 'Shadowfang Stalker', 'Prismatic Templar',
])
def test_every_class_levels_and_serializes_through_60_then_lab_61(game, player_class):
    player = game.create_player(player_class)
    for level in range(2, 61):
        for _ in range(player.unspent_stat_points):
            player.allocate_core_stat('vitality' if level % 4 == 0 else ('intelligence' if player_class in game.CASTER_CLASSES else 'strength'))
        game.gain_xp(player, player.xp_to_next - player.xp)
        assert player.level == level
        assert 0 < player.hp <= player.max_hp and 0 <= player.mana <= player.max_mana
        assert game.Player.from_dict(player.to_dict()).to_dict() == player.to_dict()
    game.gain_xp(player, player.xp_to_next - player.xp, level_cap=None)
    assert player.level == 61


def test_entire_local_prestige_path_keeps_other_chronicles_and_purchased_companion(game, monkeypatch):
    monkeypatch.setattr(game, 'DESKTOP_MODE', True)
    state = state_for(game)
    assert state.create_labyrinth_solo_session()
    assert state.labyrinth_buy_roster_companion('Black Guard')
    roster_before = copy.deepcopy(state.labyrinth_roster_companions)
    state.leave_labyrinth_session()
    other_before = copy.deepcopy(state.slots[1:])
    path = game.season_class_order(state.current_slot_season_id())
    current = path[0]
    completed = []
    while True:
        state.unlocked_classes.add(current)
        state.start_game(current)
        while state.player.level < 60:
            game.gain_xp(state.player, state.player.xp_to_next - state.player.xp)
        state.player.gold = 2000
        state.sync_active_slot()
        state.finish_masterquest_attempt(True)
        completed.append(current)
        next_class = game.season_class_masterquest_next(state.current_slot_season_id()).get(current)
        if next_class is None:
            break
        assert next_class in state.unlocked_classes
        assert state.player is None
        current = next_class
    assert state.player is not None
    assert state.slots[1:] == other_before
    assert state.labyrinth_roster_companions == roster_before
    assert len(completed) >= 8


@pytest.mark.parametrize('level', [1, 15, 30, 45, 60])
def test_every_roster_class_has_valid_arena_combat_at_key_progression_levels(game, level):
    for player_class in sorted(game.KNOWN_CLASS_NAMES):
        random.seed(20261026 + level)
        if level >= 45:
            player = game._labyrinth_build_companion_player(player_class, level)
        else:
            player = game.create_player(player_class)
            while player.level < level:
                game.gain_xp(player, player.xp_to_next - player.xp)
        monster, _ = game.generate_monster(level, forced_level=level, player_class=player_class)
        assert game.build_combat_timeline(player, monster)
        assert 0 <= player.hp <= player.max_hp
        assert 0 <= player.mana <= player.max_mana


def test_desktop_lab_profile_uses_live_state_without_normalizing_saved_checkpoint(game, monkeypatch):
    monkeypatch.setattr(game, 'DESKTOP_MODE', True)
    state = state_for(game)
    state.player.inventory = [sample_item(game)]
    state.sync_active_slot()
    def unnecessary_normalization(_slot):
        raise AssertionError('Lab HUD must not repeatedly normalize the full saved checkpoint')
    monkeypatch.setattr(game, 'normalize_slot_payload', unnecessary_normalization)
    profile = game._labyrinth_profile_payload_for_current_player(state)
    assert profile['level'] == state.player.level
    assert profile['inventory_items'][0] == state.player.inventory[0].to_dict()
    payload = game._labyrinth_member_payload(state)
    assert payload['level'] == state.player.level
    assert state.current_account_ladder_resets() == 0


def test_complete_seven_by_seven_lab_floor_and_boss_reward_loop(game, monkeypatch):
    monkeypatch.setattr(game, 'DESKTOP_MODE', True)
    state = state_for(game)
    assert state.create_labyrinth_solo_session()
    for player_class in ['Night Angel', 'Shadow Mage', 'Warlock', 'Prismatic Templar']:
        assert state.labyrinth_hire_companion(player_class)
    assert state.labyrinth_start_floor()
    start_level, start_gold = state.player.level, state.player.gold

    def resolve():
        if state.labyrinth_session_row['status'] in {'encounter', 'boss'}:
            pending = state.labyrinth_session_row['pending_encounter']
            for monster in pending['monster_snapshots']:
                monster.update(hp=1, physical_armor=0, magic_resistance=0, evasion=0)
            for _ in range(10):
                if state.labyrinth_session_row['status'] not in {'encounter', 'boss'}:
                    break
                assert state.run_labyrinth_encounter(ignore_timing=True)
            assert state.labyrinth_session_row['status'] in {'exploring', 'reward'}

    def move(direction):
        assert state.labyrinth_move_party(direction)
        resolve()

    for _ in range(3):
        move('left')
    for _ in range(3):
        move('up')
    for row in range(7):
        for _ in range(6):
            move('right' if row % 2 == 0 else 'left')
        if row < 6:
            move('down')
    assert state.labyrinth_session_row['status'] == 'reward'
    assert state.player.level == start_level + 1
    assert 100 <= state.player.gold - start_gold <= 150
    assert len(state.labyrinth_session_row['reward_options']) == 3
    assert state.vote_labyrinth_reward(0)
    if state.labyrinth_session_row['status'] == 'reward':
        assert state.finalize_labyrinth_reward_vote()
    assert state.labyrinth_session_row['floor'] == 2
    assert state.labyrinth_session_row['status'] == 'exploring'


def test_desktop_page_reload_reuses_single_live_state(game, monkeypatch):
    monkeypatch.setattr(game, 'DESKTOP_MODE', True)
    monkeypatch.setattr(game, 'DESKTOP_ACTIVE_STATE', None)
    first = game.page_session_state()
    first.player = game.create_player('Black Guard')
    first.player.gold = 777
    assert game.page_session_state() is first
    assert game.page_session_state().player.gold == 777


def test_desktop_tank_toggle_survives_repeated_slot_and_profile_updates(game, monkeypatch):
    monkeypatch.setattr(game, 'DESKTOP_MODE', True)
    state = state_for(game)
    assert state.create_labyrinth_solo_session()
    assert state.labyrinth_hire_companion('Shadow Mage')
    assert state.labyrinth_start_floor()
    ids = [row['user_id'] for row in state.labyrinth_member_rows]
    for member_id in ids:
        assert state.labyrinth_set_tank_role(member_id, True)
        assert [row['user_id'] for row in state.labyrinth_member_rows] == ids
        for _ in range(3):
            state.sync_active_slot()
            row = next(row for row in state.labyrinth_member_rows if row['user_id'] == member_id)
            assert row['tank'] is True
            assert game._labyrinth_project_member_row(row, game._labyrinth_party_state_map(state.labyrinth_session_row['pending_encounter']))['tank'] is True
        assert state.labyrinth_set_tank_role(member_id, False)


def test_desktop_chronicles_do_not_inherit_another_slots_season_or_reset(game, monkeypatch):
    monkeypatch.setattr(game, 'DESKTOP_MODE', True)
    state = state_for(game)
    state.slots = [game.build_default_slot_payload(season) for season in (1, 2, 3)]
    for slot in state.slots:
        slot['player'] = game.create_player(game.season_feeder_classes(slot['season_id'])[0]).to_dict()
    state.current_global_season_id = 99
    state.global_ladder_reset_count = 98
    before = copy.deepcopy(state.slots)
    assert not state.apply_pending_global_season_reset()
    assert state.slots == before
    state.open_slot(0)
    assert state.player is not None
    assert state.current_slot_season_id() == 1
    state.sync_active_slot()
    assert state.slots[0]['season_id'] == 1
    assert state.slots[1:] == before[1:]
