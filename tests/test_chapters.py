import asyncio
import copy
import json
from collections import Counter
from unittest.mock import patch

import pytest
from test_runtime_regressions import sample_item, state_for

from steam_client.chapters import Ascension, ChapterError, Market
from steam_client.transactions import DesktopTransactionError


def inventory_counts(state):
    items = list(state.vault_items)
    if state.player:
        items += list(state.player.inventory) + [i for i in state.player.equipped.values() if i]
    else:
        items += list(state.shared_inventory)
    for category in state.saved_item_sets.values():
        items.extend(category.values())
    return Counter(json.dumps(i.to_dict(), sort_keys=True) for i in items)


def market_for(game):
    state = state_for(game)
    state.game_tab = 'marketplace'
    state.marketplace_offers = [game.MarketplaceOffer(sample_item(game, str(i)), 100+i) for i in range(3)]
    return state, Market(state, game)


def test_market_selection_never_spends_or_auto_equips(game):
    state, market = market_for(game)
    before = state.player.to_dict()
    assert market.selected is None
    market.select(state.marketplace_offers[1])
    market.arm()
    assert state.player.to_dict() == before


def test_market_owns_exact_offer_and_buys_once_after_reordering(game):
    state, market = market_for(game)
    offer = state.marketplace_offers[0]
    market.select(offer)
    market.arm()
    state.marketplace_offers.reverse()
    receipt = market.buy()
    assert receipt.owned_item is offer.item
    assert state.player.gold == 9900
    assert state.player.inventory[-1] is offer.item and offer.sold
    with pytest.raises(ChapterError):
        market.buy()


@pytest.mark.parametrize('change', ['price', 'stock', 'item', 'gold'])
def test_market_stale_confirmation_is_not_a_different_purchase(game, change):
    state, market = market_for(game)
    offer = state.marketplace_offers[0]
    market.select(offer)
    market.arm()
    if change == 'price':
        offer.price += 1
    elif change == 'stock':
        state.marketplace_offers[0] = game.MarketplaceOffer(copy.deepcopy(offer.item), 100)
    elif change == 'item':
        offer.item.affix_stats['strength'] += 1
    else:
        state.player.gold = 0
    before = state.player.to_dict()
    with pytest.raises(ChapterError):
        market.buy()
    assert state.player.to_dict() == before


def test_market_save_failure_rolls_back_wallet_inventory_and_sold_flag(game, monkeypatch):
    state, market = market_for(game)
    monkeypatch.setattr(game, 'DESKTOP_MODE', True)
    before = state.player.to_dict()
    state.persist_to_disk = lambda **kw: (_ for _ in ()).throw(OSError('disk full'))
    market.select(state.marketplace_offers[0])
    market.arm()
    with pytest.raises(DesktopTransactionError):
        market.buy()
    assert state.player.to_dict() == before
    assert not state.marketplace_offers[0].sold and market.receipt is None


def rite_for(game, cls='Black Guard'):
    state = state_for(game, cls, 60)
    state.game_tab = 'masterquest'
    state.player.inventory = [sample_item(game)]
    state.sync_active_slot()
    return state, Ascension(state, game)


def test_ascension_threshold_is_read_only_and_entry_is_once(game):
    state, rite = rite_for(game, 'Solaris Paladin')
    gold = state.player.gold
    before = state.player.to_dict()
    assert rite.brief()['cost'] == game.masterquest_attempt_cost(state.player.player_class)
    assert state.player.to_dict() == before
    rite.enter()
    assert state.player.gold == gold - game.masterquest_attempt_cost(state.player.player_class)
    with pytest.raises(ChapterError):
        rite.enter()


def test_entry_write_failure_does_not_charge_or_start_rite(game):
    state, rite = rite_for(game, 'Solaris Paladin')
    before = state.player.to_dict()
    state.persist_to_disk = lambda **kw: (_ for _ in ()).throw(OSError('disk full'))
    with pytest.raises(DesktopTransactionError):
        rite.enter()
    assert state.player.to_dict() == before
    assert not rite.started


def test_invalid_vessel_and_unselected_light_do_not_end_run(game):
    state, rite = rite_for(game)
    rite.enter()
    with pytest.raises(ChapterError):
        asyncio.run(rite.offer('not-a-vessel', lambda: None))
    with pytest.raises(ChapterError):
        asyncio.run(rite.offer(state.masterquest_container_order[0], lambda: None))
    assert state.player is not None and rite.receipt is None


@pytest.mark.parametrize('passed,cls', [(False,'Black Guard'),(True,'Black Guard'),(True,'Prismatic Sorceress')])
def test_rite_keeps_original_outcome_and_preserves_other_chronicles(game, monkeypatch, passed, cls):
    monkeypatch.setattr(game, 'DESKTOP_MODE', True)
    state, rite = rite_for(game, cls)
    state.slots[1]['player'] = game.create_player('Shadow Mage').to_dict()
    others = copy.deepcopy(state.slots[1:])
    items = inventory_counts(state)
    rite.enter()
    async def immediate(_seconds):
        return None
    async def solve():
        for essence in list(state.masterquest_essence_order):
            rite.select(essence)
            vessel = state.masterquest_solution[essence]
            if not passed:
                vessel = next(v for v in state.masterquest_container_order if v != vessel)
            await rite.offer(vessel, lambda: None)
            if rite.receipt:
                break
    with patch.object(rite, '_pause', immediate):
        asyncio.run(solve())
    assert rite.receipt.passed == passed
    assert state.slots[1:] == others
    assert inventory_counts(state) == items
    assert state.slots[0]['pq_ledger_entries'][0]['passed'] == passed
    assert not state.masterquest_result_popup_open
    assert (state.player is not None) == (passed and cls == 'Prismatic Sorceress')
    if passed and cls != 'Prismatic Sorceress':
        assert rite.receipt.next_class in state.unlocked_classes
    assert not rite.acknowledged
    rite.acknowledge()
    assert rite.acknowledged


def test_rite_does_not_leak_hidden_solution_into_presentation(game):
    state, rite = rite_for(game)
    rite.enter()
    signal = rite.signal()
    assert 'solution' not in signal and 'correct' not in signal
    assert signal['phase'] == 'ritual'
    essence = state.masterquest_essence_order[0]
    rite.select(essence)
    rite.select(essence)
    assert not state.masterquest_active_essence()


def test_failed_settlement_can_retry_without_double_ledger_or_item_loss(game, monkeypatch):
    monkeypatch.setattr(game, 'DESKTOP_MODE', True)
    state, rite = rite_for(game)
    rite.enter()
    before = inventory_counts(state)
    state.persist_to_disk = lambda **kw: (_ for _ in ()).throw(OSError('disk full'))
    async def immediate(_seconds):
        return None
    essence = state.masterquest_essence_order[0]
    rite.select(essence)
    wrong = next(v for v in state.masterquest_container_order if v != state.masterquest_solution[essence])
    with patch.object(rite, '_pause', immediate):
        asyncio.run(rite.offer(wrong, lambda: None))
    assert rite.receipt is None and rite.pending_verdict is False
    assert state.player is not None and inventory_counts(state) == before
    assert not state.slots[0].get('pq_ledger_entries')
    state.persist_to_disk = lambda **kw: None
    rite.retry_settlement()
    assert rite.receipt is not None and not rite.receipt.passed
    assert len(state.slots[0]['pq_ledger_entries']) == 1
    assert inventory_counts(state) == before
    with pytest.raises(ChapterError):
        rite.retry_settlement()


@pytest.mark.parametrize('cls,count', [('Black Guard',3),('Monk of Selune',4),('Warlock',5),('Prismatic Sorceress',6)])
def test_all_rite_sizes_use_original_permutations(game, cls, count):
    state, rite = rite_for(game, cls)
    rite.enter()
    assert len(state.masterquest_solution) == count == rite.brief()['count']
    assert set(state.masterquest_solution) == set(state.masterquest_essence_order)
    assert set(state.masterquest_solution.values()) == set(state.masterquest_container_order)


def test_rite_duplicate_click_during_judgment_is_ignored(game):
    state, rite = rite_for(game)
    rite.enter()
    light = state.masterquest_essence_order[0]
    rite.select(light)
    vessel = state.masterquest_solution[light]
    async def exercise():
        task = asyncio.create_task(rite.offer(vessel, lambda: None))
        await asyncio.sleep(.01)
        assert rite.busy
        await rite.offer(vessel, lambda: None)
        with pytest.raises(ChapterError):
            rite.select(light)
        await task
    asyncio.run(exercise())
    assert rite.sequence == 1 and len(state.masterquest_matched_essences) == 1
    assert not rite.busy and rite.receipt is None


def test_aiming_is_free_and_explicit_commit_is_required(game):
    state, rite = rite_for(game)
    rite.enter()
    before = state.player.to_dict()
    light = state.masterquest_essence_order[0]
    rite.select(light)
    rite.aim(state.masterquest_container_order[0])
    assert rite.target_vessel and rite.sequence == 0
    assert state.player.to_dict() == before and not state.masterquest_matched_essences
    rite.select(state.masterquest_essence_order[1])
    assert not rite.target_vessel


def test_cancelled_offering_can_only_resume_its_committed_pair(game):
    state, rite = rite_for(game)
    rite.enter()
    light = state.masterquest_essence_order[0]
    vessel = state.masterquest_solution[light]
    rite.select(light)
    async def exercise():
        task = asyncio.create_task(rite.offer(vessel, lambda: None))
        await asyncio.sleep(.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not rite.busy and rite.offering is not None
        with pytest.raises(ChapterError):
            rite.select(state.masterquest_essence_order[1])
        async def instant(_seconds):
            return None
        rite._pause = instant
        await rite.resume(lambda: None)
    asyncio.run(exercise())
    assert rite.sequence == 1 and state.masterquest_matched_essences == {light}
    assert rite.offering is None and not rite.busy


def test_ui_refresh_exception_does_not_abort_an_offering(game):
    state, rite = rite_for(game)
    rite.enter()
    light = state.masterquest_essence_order[0]
    rite.select(light)
    async def instant(_seconds):
        return None
    rite._pause = instant
    def broken_view():
        raise RuntimeError('deleted slot')
    asyncio.run(rite.offer(state.masterquest_solution[light], broken_view))
    assert state.masterquest_matched_essences == {light} and not rite.busy
    assert rite.offering is None


def test_quick_reveal_changes_timing_not_the_committed_outcome(game):
    state, rite = rite_for(game)
    rite.enter()
    light = state.masterquest_essence_order[0]
    rite.select(light)
    async def exercise():
        task = asyncio.create_task(rite.offer(state.masterquest_solution[light], lambda: None))
        await asyncio.sleep(.01)
        rite.quick_reveal()
        await asyncio.wait_for(task, .5)
    asyncio.run(exercise())
    assert state.masterquest_matched_essences == {light} and rite.sequence == 1


def test_receipt_failure_cannot_commit_then_record_a_second_attempt(game, monkeypatch):
    from steam_client import chapters
    monkeypatch.setattr(game, 'DESKTOP_MODE', True)
    state, rite = rite_for(game)
    rite.enter()
    items = inventory_counts(state)
    original = chapters.AscensionResult
    monkeypatch.setattr(chapters, 'AscensionResult', lambda *args: (_ for _ in ()).throw(ValueError('receipt error')))
    with pytest.raises(DesktopTransactionError):
        rite._settle(False, state.finish_masterquest_attempt)
    assert state.player is not None and inventory_counts(state) == items
    assert not state.slots[0].get('pq_ledger_entries')
    monkeypatch.setattr(chapters, 'AscensionResult', original)
    rite.retry_settlement()
    assert len(state.slots[0]['pq_ledger_entries']) == 1


def test_stale_commit_cannot_risk_a_newly_changed_pair(game):
    state, rite = rite_for(game)
    rite.enter()
    light = state.masterquest_essence_order[0]
    rite.select(light)
    first, second = state.masterquest_container_order[:2]
    rite.aim(first)
    rite.aim(second)
    with pytest.raises(ChapterError, match='pairing changed'):
        asyncio.run(rite.commit(light, first, lambda: None))
    assert rite.sequence == 0 and rite.offering is None
