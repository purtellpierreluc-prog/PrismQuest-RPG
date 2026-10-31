import asyncio
import copy
from unittest.mock import AsyncMock, Mock, patch

import pytest
from test_runtime_regressions import state_for

from steam_client.well import WellError, well_for


def fixture(game, monkeypatch):
    monkeypatch.setattr(game,'DESKTOP_MODE',True)
    state = state_for(game)
    state.game_tab = 'well'
    item = game.Item('Offering','weapon',15,'Common','Axe',{'attack_damage_min':18,'attack_damage_max':22},{})
    state.player.inventory = [item,copy.deepcopy(item)]
    state._animate_monster_page_turn_async = AsyncMock()
    state._run_arena_combat_async = AsyncMock()
    return state,well_for(state,game),item


def test_browsing_and_confirmation_spend_nothing(game,monkeypatch):
    state,well,item = fixture(game,monkeypatch)
    before = state.player.to_dict()
    well.select(item)
    well.arm()
    assert state.player.to_dict() == before


def test_entry_consumes_only_exact_reviewed_item_once(game,monkeypatch):
    state,well,item = fixture(game,monkeypatch)
    other = state.player.inventory[1]
    well.select(item)
    well.arm()
    state.player.inventory.reverse()
    asyncio.run(well.commit(lambda:None))
    assert state.player.gold == 9990 and state.player.inventory == [other]
    assert state.pending_well_sacrifice_item.to_dict() == item.to_dict()
    with pytest.raises(WellError):
        asyncio.run(well.commit(lambda:None))


@pytest.mark.parametrize('change',['removed','mutated','gold'])
def test_stale_offering_never_consumes_another_item(game,monkeypatch,change):
    state,well,item = fixture(game,monkeypatch)
    well.select(item)
    well.arm()
    if change == 'removed':
        state.player.inventory.pop(0)
    elif change == 'mutated':
        item.level = 20
    else:
        state.player.gold = 0
    before = state.player.to_dict()
    with pytest.raises(WellError):
        asyncio.run(well.commit(lambda:None))
    assert state.player.to_dict() == before


def test_failed_entry_restores_gold_item_coffers_and_no_fight(game,monkeypatch):
    state,well,item = fixture(game,monkeypatch)
    before = state.player.to_dict()
    coffers = state.local_town_service_spend
    state.persist_to_disk = Mock(side_effect=OSError('disk full'))
    well.select(item)
    well.arm()
    with pytest.raises(WellError):
        asyncio.run(well.commit(lambda:None))
    assert state.player.to_dict() == before
    assert state.local_town_service_spend == coffers and not state.fight_in_progress
    assert state.pending_well_sacrifice_item is None


def prepare_finish(game,state):
    state.current_monster,_ = game.generate_well_monster(state.player.level)
    state.current_monster.hp = 0
    state.current_monster_xp = 0
    state.current_encounter_type = 'well'
    state.fight_in_progress = True
    state.player.wins += 1


@pytest.mark.parametrize('found',[True,False])
def test_real_victory_preserves_half_chance_and_same_tier_type(game,monkeypatch,found):
    state,well,item = fixture(game,monkeypatch)
    well.select(item)
    well.arm()
    asyncio.run(well.commit(lambda:None))
    prepare_finish(game,state)
    reward = game.Item('Answer','weapon',15,'Epic','Axe',{'attack_damage_min':18,'attack_damage_max':22},{'strength':10})
    with patch.object(game.random,'random',return_value=.1 if found else .9), patch.object(game,'generate_well_item_drop',return_value=reward):
        asyncio.run(state._finish_arena_fight_async(lambda:None))
    assert state.game_tab == 'well' and not state.fight_in_progress
    assert len(state.player.inventory) == (2 if found else 1)
    assert well.receipt.outcome == ('item' if found else 'miss')
    if found:
        assert well.receipt.owned_item is reward and well.receipt.item is not reward
        assert well.receipt.item.level == item.level and well.receipt.item.subtype == item.subtype


def test_failed_outcome_save_retries_same_roll_once_without_refunding_entry(game,monkeypatch):
    state,well,item = fixture(game,monkeypatch)
    well.select(item)
    well.arm()
    asyncio.run(well.commit(lambda:None))
    prepare_finish(game,state)
    reward = game.generate_specific_item(15,'weapon','Axe','Epic')
    state.persist_to_disk = Mock(side_effect=OSError('disk full'))
    with patch.object(game.random,'random',return_value=.1), patch.object(game,'generate_well_item_drop',return_value=reward) as generate:
        asyncio.run(state._finish_arena_fight_async(lambda:None))
        assert well.pending and len(state.player.inventory) == 1 and state.player.gold == 9990
        state.persist_to_disk = Mock()
        asyncio.run(well.retry_settlement(lambda:None))
        assert generate.call_count == 1
    assert not well.pending and well.receipt.outcome == 'item'
    assert len(state.player.inventory) == 2 and state.player.gold == 9990
    assert state.ladder_stats[state.player.player_class]['wellspawns_killed'] == 1


def test_battle_error_never_refunds_a_committed_offering(game,monkeypatch):
    state,well,item = fixture(game,monkeypatch)
    state._run_arena_combat_async = AsyncMock(side_effect=RuntimeError('interrupted view'))
    well.select(item)
    well.arm()
    asyncio.run(well.commit(lambda:None))
    assert state.player.gold == 9990 and len(state.player.inventory) == 1
    assert well.interrupted and state.current_monster is not None


def test_withdrawing_consumes_the_original_cost_without_loot(game,monkeypatch):
    state,well,item = fixture(game,monkeypatch)
    well.select(item)
    well.arm()
    asyncio.run(well.commit(lambda:None))
    asyncio.run(state._resolve_arena_flee_async(lambda:None))
    assert well.receipt.outcome == 'fled' and not well.pending
    assert state.player.gold == 9990 and len(state.player.inventory) == 1
    assert state.current_monster is None and not state.fight_in_progress


def test_defeat_never_grants_an_item_or_resets_other_chronicles(game,monkeypatch):
    state,well,item = fixture(game,monkeypatch)
    others = copy.deepcopy(state.slots[1:])
    well.select(item)
    well.arm()
    asyncio.run(well.commit(lambda:None))
    state.player.hp = 0
    asyncio.run(state._finish_arena_fight_async(lambda:None))
    assert well.receipt.outcome == 'defeat'
    assert len(state.player.inventory) == 1 and state.player.gold == 9990
    assert state.slots[1:] == others


def test_repeated_save_failure_does_not_change_outcome_or_inventory(game,monkeypatch):
    state,well,item = fixture(game,monkeypatch)
    well.select(item)
    well.arm()
    asyncio.run(well.commit(lambda:None))
    prepare_finish(game,state)
    state.persist_to_disk = Mock(side_effect=OSError('disk full'))
    with patch.object(game.random,'random',return_value=.1), patch.object(game,'generate_well_item_drop',return_value=game.generate_specific_item(15,'weapon','Axe','Epic')) as generate:
        asyncio.run(state._finish_arena_fight_async(lambda:None))
        before = state.player.to_dict()
        for _ in range(2):
            with pytest.raises(WellError):
                asyncio.run(well.retry_settlement(lambda:None))
            assert state.player.to_dict() == before and well.pending
        state.persist_to_disk = Mock()
        asyncio.run(well.retry_settlement(lambda:None))
        assert generate.call_count == 1
    with pytest.raises(WellError):
        asyncio.run(well.retry_settlement(lambda:None))
    assert len(state.player.inventory) == 2 and state.player.gold == 9990


def test_cancelled_fight_releases_busy_state_and_resumes_without_new_fee(game,monkeypatch):
    state,well,item = fixture(game,monkeypatch)
    state._run_arena_combat_async = AsyncMock(side_effect=asyncio.CancelledError())
    well.select(item)
    well.arm()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(well.commit(lambda:None))
    monster = state.current_monster
    assert not well.busy and well.interrupted and state.game_tab == 'well'
    state._run_arena_combat_async = AsyncMock()
    asyncio.run(well.resume(lambda:None))
    assert state.current_monster is monster
    assert state.player.gold == 9990 and len(state.player.inventory) == 1


def test_hardcore_defeat_preserves_original_cleanup(game,monkeypatch):
    state,well,item = fixture(game,monkeypatch)
    state.active_slot_index = 2
    well = well_for(state,game)
    well.select(item)
    well.arm()
    asyncio.run(well.commit(lambda:None))
    state.player.hp = 0
    asyncio.run(state._finish_arena_fight_async(lambda:None))
    assert state.player is None and not well.pending
    assert well.receipt.outcome == 'defeat'
    assert state.slots[2]['player'] is None
