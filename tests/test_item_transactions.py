import copy
from unittest.mock import patch

import pytest
from test_runtime_regressions import sample_item, state_for

from steam_client.storage import AtomicSaveStore
from steam_client.transactions import DesktopTransactionError


def test_failed_transmutation_keeps_gold_and_both_offerings(game):
    state = state_for(game)
    state.player.inventory = [sample_item(game, 'First'), sample_item(game, 'Second')]
    state.ensure_transmute_scene_state()
    choices = list(state.transmute_item_map())
    state.transmute_choice_one, state.transmute_choice_two = choices[:2]
    before = state.player.to_dict()
    with patch.object(game, 'generate_specific_item', side_effect=RuntimeError('roll failed')), pytest.raises(RuntimeError):
        state.transmute_selected()
    assert state.player.to_dict() == before


@pytest.mark.parametrize('action', ['sell', 'bulk_sell', 'equip', 'vault', 'saved', 'delete', 'buy_vault', 'transmute'])
def test_failed_disk_commit_rolls_back_all_item_ownership(game, tmp_path, monkeypatch, action):
    monkeypatch.setattr(game, 'DESKTOP_MODE', True)
    store = AtomicSaveStore(tmp_path / 'chronicles.json')
    monkeypatch.setattr(game, 'DESKTOP_SAVE_STORE', store)
    state = state_for(game)
    state.player.inventory = [sample_item(game, 'First'), sample_item(game, 'Second')]
    state.vault_capacity = 10
    state.persist_to_disk = lambda **_kw: store.save(state.slots)
    state.sync_active_slot()
    if action == 'transmute':
        state.ensure_transmute_scene_state()
        choices = list(state.transmute_item_map())
        state.transmute_choice_one, state.transmute_choice_two = choices[:2]
    before = copy.deepcopy(state.slots)
    before_spend = copy.deepcopy(state.local_town_service_spend)
    player = state.player.to_dict()
    actions = {
        'sell': lambda: state.sell_item(0), 'equip': lambda: state.equip_item(0),
        'vault': lambda: state.store_vault_item(0), 'saved': lambda: state.save_selected_item_to_set(0),
        'delete': lambda: state.delete_inventory_item(0), 'buy_vault': state.buy_vault_slots,
        'transmute': state.transmute_selected,
        'bulk_sell': lambda: state.sell_inventory_items([0, 1]),
    }
    with patch('steam_client.storage.os.replace', side_effect=OSError('disk full')), pytest.raises(DesktopTransactionError):
        actions[action]()
    assert state.player.to_dict() == player
    assert state.slots == before
    assert state.local_town_service_spend == before_spend
    assert store.load() == before
    assert not state.vault_items


def test_roster_transfer_failed_commit_keeps_player_and_companion_equipment(game, tmp_path, monkeypatch):
    monkeypatch.setattr(game, 'DESKTOP_MODE', True)
    state = state_for(game)
    assert state.create_labyrinth_solo_session()
    assert state.labyrinth_buy_roster_companion('Black Guard')
    companion_id = state.labyrinth_roster_companions[0]['id']
    state.player.inventory = [sample_item(game)]
    before_player = state.player.to_dict()
    before_roster = copy.deepcopy(state.labyrinth_roster_companions)
    state.persist_to_disk = lambda **_kw: (_ for _ in ()).throw(OSError('disk full'))
    with pytest.raises(DesktopTransactionError):
        state.labyrinth_set_roster_companion_item(companion_id, 'weapon', 0)
    assert state.player.to_dict() == before_player
    assert state.labyrinth_roster_companions == before_roster


def test_successful_item_transfer_has_one_durable_commit(game, monkeypatch):
    monkeypatch.setattr(game, 'DESKTOP_MODE', True)
    state = state_for(game)
    state.player.inventory = [sample_item(game)]
    state.vault_capacity = 10
    state.store_vault_item(0)
    assert state.persist_to_disk.call_count == 1
    assert len(state.vault_items) == 1 and not state.player.inventory


def test_identical_saved_item_is_not_deleted_when_equipping_companion(game):
    state = state_for(game)
    assert state.create_labyrinth_solo_session()
    assert state.labyrinth_buy_roster_companion('Black Guard')
    item = sample_item(game)
    category = game.get_saved_item_category(item)
    state.player.inventory = [item]
    state.saved_item_sets[category][45] = copy.deepcopy(item)
    companion_id = state.labyrinth_roster_companions[0]['id']
    assert state.labyrinth_set_roster_companion_item(companion_id, 'weapon', 0)
    assert state.saved_item_sets[category][45].to_dict() == item.to_dict()
    assert not state.player.inventory


def test_bulk_sale_deduplicates_indices_and_commits_once(game, monkeypatch):
    monkeypatch.setattr(game, 'DESKTOP_MODE', True)
    state = state_for(game)
    items = [sample_item(game, str(index)) for index in range(3)]
    state.player.inventory = items[:]
    before_gold = state.player.gold
    count, gold = state.sell_inventory_items([0, 0, 2, 999, -1])
    assert count == 2 and gold == items[0].sell_value() + items[2].sell_value()
    assert state.player.gold == before_gold + gold
    assert state.player.inventory == [items[1]]
    assert state.persist_to_disk.call_count == 1
