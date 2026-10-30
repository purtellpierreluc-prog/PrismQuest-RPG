"""The redesigned workbench observes the existing ritual, never rolls ahead."""

import copy
from unittest.mock import patch

import pytest
from test_runtime_regressions import sample_item, state_for

from steam_client.crucible import Crucible, CrucibleError
from steam_client.transactions import DesktopTransactionError


def bench_for(game, rarities=('Fine', 'Rare')):
    state = state_for(game)
    state.player.inventory = [sample_item(game, f'Offering {i}') for i in range(len(rarities))]
    for item, rarity in zip(state.player.inventory, rarities, strict=True):
        item.rarity = rarity
    return state, Crucible(state, game)


def ready(game, rarities=('Fine', 'Rare')):
    state, bench = bench_for(game, rarities)
    bench.choose(state.player.inventory[0])
    bench.choose(state.player.inventory[1])
    return state, bench


def test_no_automatic_or_hidden_offerings(game):
    state, bench = bench_for(game)
    assert bench.first is None and bench.second is None
    assert bench.quote().blocker
    bench.choose(state.player.inventory[0])
    assert bench.first is state.player.inventory[0]
    assert bench.second is None and bench.target == 'fuel'


def test_duplicate_rolls_are_distinct_but_same_object_cannot_fill_both_slots(game):
    state, bench = bench_for(game)
    state.player.inventory[1] = copy.deepcopy(state.player.inventory[0])
    bench.choose(state.player.inventory[0])
    with pytest.raises(CrucibleError):
        bench.choose(state.player.inventory[0])
    bench.choose(state.player.inventory[1])
    assert not bench.quote().blocker


def test_only_pack_items_and_same_tier_fine_or_better_are_allowed(game):
    state, bench = bench_for(game, ('Rare', 'Common', 'Epic'))
    with pytest.raises(CrucibleError):
        bench.choose(state.player.inventory[1])
    with pytest.raises(CrucibleError):
        bench.choose(copy.deepcopy(state.player.inventory[0]))
    bench.choose(state.player.inventory[0])
    state.player.inventory[2].level = 40
    with pytest.raises(CrucibleError):
        bench.choose(state.player.inventory[2])
    assert bench.second is None


def test_forecast_merges_identical_outcomes_without_calling_random(game):
    state, bench = ready(game)
    with patch.object(game.random, 'random', side_effect=AssertionError('forecast must not roll')):
        quote = bench.quote()
    assert {r.rarity: r.percent for r in quote.outcomes} == {'Rare': 85, 'Fine': 15}
    assert quote.cost == state.transmute_gold_cost(bench.first, bench.second)
    assert quote.tier == 45 and quote.subtype == 'Axe'


def test_forecast_matches_every_branch_of_existing_rules_for_all_rarities(game):
    rarities = [r for r in game.RARITY_ORDER if r != 'Common']
    for one in rarities:
        for two in rarities:
            _, bench = ready(game, (one, two))
            expected = {}
            for roll, weight in [(0.1, 35), (0.5, 50), (.95, 15)]:
                with patch.object(game.random, 'random', return_value=roll):
                    rarity = game.determine_transmute_rarity(bench.first, bench.second)
                expected[rarity] = expected.get(rarity, 0) + weight
            assert {r.rarity: r.percent for r in bench.quote().outcomes} == expected


def test_replacing_form_keeps_compatible_fuel_and_drops_incompatible_fuel(game):
    state, bench = ready(game, ('Fine', 'Rare', 'Epic'))
    previous = bench.second
    bench.set_target('form')
    bench.choose(state.player.inventory[2])
    assert bench.second is previous
    another = sample_item(game, 'Another tier')
    another.level = 40
    state.player.inventory.append(another)
    bench.set_target('form')
    bench.choose(another)
    assert bench.second is None


def test_explicit_confirmation_and_exactly_one_legacy_transaction(game):
    state, bench = ready(game)
    with pytest.raises(CrucibleError):
        bench.commit()
    original = tuple(state.player.inventory)
    gold = state.player.gold
    cost = bench.quote().cost
    bench.arm()
    with patch.object(state, 'transmute_selected', wraps=state.transmute_selected) as transaction:
        receipt = bench.commit()
    assert transaction.call_count == 1
    assert len(state.player.inventory) == 1
    assert state.player.gold == gold - cost
    assert all(item is not old for old in original for item in state.player.inventory)
    assert receipt.owned_item is state.player.inventory[0]
    assert receipt.item.to_dict() == receipt.owned_item.to_dict()
    assert receipt.item is not receipt.owned_item
    assert not state.transmute_reveal_active
    assert bench.first is None and bench.second is None
    with pytest.raises(CrucibleError):
        bench.commit()


@pytest.mark.parametrize('mutation', ['removed', 'changed', 'gold'])
def test_stale_confirmation_cannot_consume_a_different_item(game, mutation):
    state, bench = ready(game)
    bench.arm()
    if mutation == 'removed':
        state.player.inventory.pop(0)
    elif mutation == 'changed':
        state.player.inventory[0].affix_stats['strength'] = 999
    else:
        state.player.gold = 0
    before = state.player.to_dict()
    with pytest.raises(CrucibleError):
        bench.commit()
    assert state.player.to_dict() == before


def test_inventory_reordering_resolves_original_offerings_not_old_indices(game):
    state, bench = ready(game, ('Fine', 'Rare', 'Epic'))
    keep = state.player.inventory[2]
    bench.arm()
    state.player.inventory.reverse()
    bench.commit()
    assert len(state.player.inventory) == 2
    assert any(item is keep for item in state.player.inventory)


def test_failure_preserves_gold_items_and_does_not_publish_a_new_receipt(game, monkeypatch):
    state, bench = ready(game)
    monkeypatch.setattr(game, 'DESKTOP_MODE', True)
    state.persist_to_disk = lambda **kw: (_ for _ in ()).throw(OSError('disk full'))
    before = state.player.to_dict()
    bench.arm()
    with pytest.raises(DesktopTransactionError):
        bench.commit()
    assert state.player.to_dict() == before
    assert bench.receipt is None


def test_no_more_pair_and_result_record_never_duplicate_items(game):
    state, bench = ready(game)
    bench.arm()
    receipt = bench.commit()
    receipt.item.affix_stats['strength'] = -999
    assert state.player.inventory[0].affix_stats.get('strength') != -999
    state.player.inventory.clear()
    assert not bench.owns(receipt.owned_item)
    with pytest.raises(CrucibleError):
        bench.choose(receipt.owned_item)
