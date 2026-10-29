import asyncio
import copy
from unittest.mock import patch

import pytest
from test_runtime_regressions import sample_item, state_for

from steam_client.experience import (
    begin_battle,
    current_result,
    equipment_changes,
    finish_battle,
    journey_for,
    labyrinth_progress,
    owned_item_index,
)


def test_goal_prioritizes_survival_and_points_without_mutation(game):
    p = game.create_player('Black Guard')
    before = p.to_dict()
    assert journey_for(p).destination == 'arena'
    assert p.to_dict() == before
    p.hp = 1
    assert journey_for(p, quest_available=True).destination == 'inn'
    p.hp = p.max_hp
    p.unspent_stat_points = 5
    assert journey_for(p).destination == 'stats'


def test_goal_handles_lab_unlock_and_blocked_ascension(game):
    p = state_for(game).player
    p.unspent_stat_points = 0
    assert journey_for(p).destination == 'labyrinth'
    p.level = 60
    assert journey_for(p, quest_blocker='Need a charm').detail == 'Need a charm'
    assert journey_for(p, quest_available=True).destination == 'masterquest'


@pytest.mark.parametrize('player_class,subtype', [('Black Guard', 'Axe'), ('Warlock', 'Staff')])
def test_equipment_comparison_uses_real_recalculation_without_touching_items(game, player_class, subtype):
    p = state_for(game, player_class).player
    item = game.generate_specific_item(45, 'weapon', subtype, 'Rare')
    item.affix_stats.update(max_health=1000, crit_chance=.05)
    before, item_before = p.to_dict(), item.to_dict()
    reason, changes = equipment_changes(p, item, game.can_player_equip_item)
    expected = copy.deepcopy(p)
    expected.equipped['weapon'] = item
    expected.recalculate_stats()
    hp = next(change for change in changes if change.label == 'Max health')
    assert not reason and hp.after == expected.max_hp and hp.before == p.max_hp
    assert p.to_dict() == before and item.to_dict() == item_before


def test_comparison_does_not_label_every_high_rarity_item_an_upgrade(game):
    p = state_for(game).player
    p.equipped['weapon'] = game.generate_specific_item(45, 'weapon', 'Axe', 'Epic')
    p.recalculate_stats()
    weak = game.generate_specific_item(1, 'weapon', 'Axe', 'Common')
    reason, changes = equipment_changes(p, weak, game.can_player_equip_item)
    assert not reason
    assert any(change.delta < 0 for change in changes)


def test_incompatible_item_explains_requirement(game):
    p = game.create_player('Black Guard')
    item = sample_item(game)
    reason, changes = equipment_changes(p, item, game.can_player_equip_item)
    assert 'Requires level' in reason and changes == []


def test_item_review_distinguishes_identical_rolls_and_rejects_stale_references(game):
    p = state_for(game).player
    a, b = sample_item(game), sample_item(game)
    p.inventory = [a, b]
    assert a == b
    assert owned_item_index(p, b) == 1
    p.inventory.pop(1)
    assert owned_item_index(p, b) is None
    assert owned_item_index(p, a) == 0


def test_receipt_is_read_only_exact_once_and_slot_scoped(game):
    state = state_for(game)
    p = state.player
    old = sample_item(game)
    p.inventory = [old]
    begin_battle(state)
    drop = sample_item(game)
    p.inventory.append(drop)
    xp = 50
    p.xp += xp
    state.fight_in_progress = False
    state.last_fight_outcome = 'victory'
    state.last_monster_snapshot = game.generate_monster(45)[0]
    before = p.to_dict()
    finish_battle(state, game.xp_to_next_for_level)
    receipt = current_result(state)
    assert receipt.xp == xp and receipt.item is drop
    finish_battle(state, game.xp_to_next_for_level)
    assert current_result(state) is receipt and p.to_dict() == before
    state.active_slot_index = 1
    assert current_result(state) is None
    state.active_slot_index = 0
    state.player.player_class = 'Warlock'
    assert current_result(state) is None


def test_receipt_handles_level_rollover(game):
    state = state_for(game, level=1)
    state.player.xp = state.player.xp_to_next - 10
    begin_battle(state)
    game.gain_xp(state.player, 35)
    state.last_fight_outcome = 'victory'
    state.fight_in_progress = False
    finish_battle(state, game.xp_to_next_for_level)
    assert current_result(state).xp == 35
    assert current_result(state).levels == 1


def test_actual_payout_observer_does_not_confuse_simulator_copies_with_new_drops(game, monkeypatch):
    monkeypatch.setattr(game, 'DESKTOP_MODE', True)
    state = state_for(game, level=2)
    state.game_tab = 'arena'
    state.player.inventory = [sample_item(game)]
    begin_battle(state)
    state.player = copy.deepcopy(state.player)
    state.current_monster = game.generate_monster(2)[0]
    state.current_monster.hp = 0
    state.current_monster_xp = 40
    state.current_encounter_type = 'normal'
    state.fight_in_progress = True
    with patch.object(game.random, 'random', return_value=0):
        asyncio.run(state._finish_arena_fight_async(lambda: None))
    result = current_result(state)
    assert result and result.outcome == 'victory'
    assert len(state.player.inventory) == 2
    assert result.item is state.player.inventory[-1]


def test_lab_progress_counts_resolved_tiles_not_generated_tiles():
    row = {'grid_size': 7, 'tile_states': {'0,0': {'resolved': True}, '1,0': {'visited': True}, '2,0': {'visited': False}}}
    assert labyrinth_progress(row) == (1, 49)
