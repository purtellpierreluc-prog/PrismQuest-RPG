import copy
from collections import Counter
from unittest.mock import Mock

import pytest
from test_runtime_regressions import sample_item, state_for

from steam_client.chapters import fingerprint
from steam_client.community import TownError, town_for
from steam_client.save_schema import owned_items, validate_slots
from steam_client.storage import AtomicSaveStore, UnsupportedSaveVersion
from steam_client.transactions import DesktopTransactionError


def fixture(game,monkeypatch):
    monkeypatch.setattr(game,'DESKTOP_MODE',True)
    state = state_for(game)
    state.game_tab = 'bazaar'
    state.player.inventory = [sample_item(game,'One'),sample_item(game,'One')]
    state.sync_active_slot()
    return state,town_for(state,game)


def counts(slots):
    return Counter(str(sorted(item.items())) for slot in slots for _,item in owned_items(slot))


def test_listing_removes_only_exact_pack_item_and_return_cannot_duplicate(game,monkeypatch):
    state,town = fixture(game,monkeypatch)
    selected,other = state.player.inventory
    state.selected_inventory_key,state.hovered_inventory_key = 'inventory:0','inventory:0'
    state.inn_vault_inventory_selected_index = 0
    before = counts(state.slots)
    listing = town.post(selected,123,fingerprint(selected))
    assert state.player.inventory == [other] and state.player.inventory[0] is other
    assert not state.selected_inventory_key and not state.hovered_inventory_key
    assert state.inn_vault_inventory_selected_index == -1
    assert counts(state.slots) == before
    town.cancel(listing['id'],listing['revision'])
    assert counts(state.slots) == before and len(state.player.inventory) == 2
    with pytest.raises(TownError):
        town.cancel(listing['id'],listing['revision'])


def test_stale_or_mutated_pack_reference_never_sacrifices_a_similar_item(game,monkeypatch):
    state,town = fixture(game,monkeypatch)
    selected = state.player.inventory.pop(0)
    with pytest.raises(TownError):
        town.post(selected,123,fingerprint(selected))
    actual = state.player.inventory[0]
    stamp = fingerprint(actual)
    actual.level = 20
    with pytest.raises(TownError):
        town.post(actual,123,stamp)
    assert state.player.inventory == [actual]


@pytest.mark.parametrize('price',[0,-1,1.5,True,1_000_001,float('inf')])
def test_listing_price_is_strictly_bounded(game,monkeypatch,price):
    state,town = fixture(game,monkeypatch)
    before = copy.deepcopy(state.slots)
    with pytest.raises(TownError):
        town.post(state.player.inventory[0],price)
    assert state.slots == before


def test_reprice_is_saved_once_and_stale_price_changes_are_rejected(game,monkeypatch):
    state,town = fixture(game,monkeypatch)
    listing = town.post(state.player.inventory[0],100)
    town.reprice(listing['id'],1,222)
    assert town.listings()[0]['price'] == 222
    with pytest.raises(TownError):
        town.reprice(listing['id'],1,333)
    assert game.normalize_slot_payload(state.slots[0])['town_services']['listings'][0]['price'] == 222


def test_failed_listing_save_preserves_items_escrow_and_coffers(game,monkeypatch):
    state,town = fixture(game,monkeypatch)
    before = copy.deepcopy(state.slots)
    item = state.player.inventory[0]
    state.persist_to_disk = Mock(side_effect=OSError('disk full'))
    with pytest.raises(DesktopTransactionError):
        town.post(item,123)
    assert state.slots == before and len(state.player.inventory) == 2
    assert not town.listings()


def test_ssf_has_no_bazaar_mutations(game,monkeypatch):
    state,_town = fixture(game,monkeypatch)
    state.active_slot_index = 1
    with pytest.raises(TownError):
        town_for(state,game).post(state.player.inventory[0],123)


def test_guild_charter_uses_main_game_fee_and_persistent_town_tally(game,monkeypatch):
    state,town = fixture(game,monkeypatch)
    guild = town.found('Quiet Lanterns','Keep the hearth lit.')
    assert state.player.gold == 9000
    assert state.local_town_service_spend == {'guild_charter':1000}
    assert town.guild()['id'] == guild['id']
    slot = game.normalize_slot_payload(state.slots[0])
    assert slot['town_services']['guild_id'] == guild['id']
    with pytest.raises(TownError):
        town.found('Another Hall','')
    assert state.player.gold == 9000


def test_guild_messages_do_not_spend_gold_or_allow_html_injection(game,monkeypatch):
    state,town = fixture(game,monkeypatch)
    town.found('Quiet Lanterns','')
    town.message('<script>not executable</script>')
    assert town.guild()['messages'][0]['body'] == '<script>not executable</script>'
    assert state.player.gold == 9000
    assert town.guild()['members'][0]['name'] == state.player.name


def test_read_only_browsing_never_initializes_or_spends(game,monkeypatch):
    state,town = fixture(game,monkeypatch)
    before = copy.deepcopy(state.slots)
    town.listings()
    town.guild()
    town.ladder()
    assert state.slots == before


def test_escrow_counts_as_ownership_but_ledger_copies_do_not(game,monkeypatch):
    state,town = fixture(game,monkeypatch)
    before = counts(state.slots)
    row = town.post(state.player.inventory[0],123)
    validate_slots(state.slots)
    assert counts(state.slots) == before
    town.cancel(row['id'],1)
    assert counts(state.slots) == before


def test_active_carryover_mirror_is_not_a_second_owned_pack(game,monkeypatch):
    state,_town = fixture(game,monkeypatch)
    item = state.player.inventory[0].to_dict()
    slot = game.build_default_slot_payload()
    slot['player'] = {'inventory':[item],'equipped':{}}
    slot['carryover_inventory'] = [copy.deepcopy(item)]
    assert len(list(owned_items(slot))) == 1
    slot['player'] = None
    assert len(list(owned_items(slot))) == 1


def buyer_fixture(game,monkeypatch):
    state,seller = fixture(game,monkeypatch)
    monkeypatch.setattr(game,'slot_mode_for_index',lambda index:'SSF' if index == 1 else 'Core')
    row = seller.post(state.player.inventory[0],123)
    state.open_slot(2)
    state.player = game.create_player('Black Guard')
    state.player.name,state.player.gold = 'Actual Buyer',500
    state.sync_active_slot()
    return state,town_for(state,game),row


def test_local_buy_pays_both_parties_once_and_conserves_items(game,monkeypatch):
    state,buyer,row = buyer_fixture(game,monkeypatch)
    before = counts(state.slots)
    buyer.buy(row['id'],1,123)
    assert state.player.gold == 377 and state.slots[0]['player']['gold'] == 10123
    assert counts(state.slots) == before
    assert state.slots[0]['town_services']['ledger'][0]['kind'] == 'Sold'
    assert state.slots[2]['town_services']['ledger'][0]['kind'] == 'Bought'
    with pytest.raises(TownError):
        buyer.buy(row['id'],1,123)
    assert counts(state.slots) == before and state.player.gold == 377


def test_failed_purchase_rolls_back_buyer_seller_and_escrow_together(game,monkeypatch):
    state,buyer,row = buyer_fixture(game,monkeypatch)
    before = copy.deepcopy(state.slots)
    state.persist_to_disk = Mock(side_effect=OSError('disk full'))
    with pytest.raises(DesktopTransactionError):
        buyer.buy(row['id'],1,123)
    assert state.slots == before and state.player.gold == 500


def test_stale_purchase_price_cannot_spend_gold(game,monkeypatch):
    state,buyer,row = buyer_fixture(game,monkeypatch)
    before = copy.deepcopy(state.slots)
    with pytest.raises(TownError):
        buyer.buy(row['id'],1,122)
    assert state.slots == before


def test_guild_join_leave_and_founder_guard_use_real_local_members(game,monkeypatch):
    state,founder = fixture(game,monkeypatch)
    charter = founder.found('Quiet Lanterns','')
    state.open_slot(1)
    state.player = game.create_player('Shadow Mage')
    state.player.name = 'Self Found Friend'
    state.sync_active_slot()
    member = town_for(state,game)
    member.join(charter['code'])
    assert len(member.guild()['members']) == 2
    state.open_slot(0)
    with pytest.raises(TownError):
        town_for(state,game).leave()
    state.open_slot(1)
    town_for(state,game).leave()
    state.open_slot(0)
    town_for(state,game).leave()
    assert not town_for(state,game).guild()
    validate_slots(state.slots)


def test_failed_charter_save_never_charges_or_creates_a_guild(game,monkeypatch):
    state,town = fixture(game,monkeypatch)
    before = copy.deepcopy(state.slots)
    state.persist_to_disk = Mock(side_effect=OSError('disk full'))
    with pytest.raises(DesktopTransactionError):
        town.found('Quiet Lanterns','')
    assert state.slots == before and state.player.gold == 10000 and town.guild() is None
    assert state.local_town_service_spend == {}


def test_town_records_and_exact_escrow_survive_disk_and_slot_reload(game,monkeypatch,tmp_path):
    state,town = fixture(game,monkeypatch)
    row = town.post(state.player.inventory[0],123)
    town.found('Quiet Lanterns','Kept across climbs.')
    town.message('A real saved message.')
    store = AtomicSaveStore(tmp_path/'chronicles.json')
    store.save(state.slots)
    restored = state_for(game)
    restored.slots = store.load()
    restored.open_slot(0)
    reloaded = town_for(restored,game)
    assert reloaded.guild()['messages'][0]['body'] == 'A real saved message.'
    assert reloaded.listings()[0]['id'] == row['id']
    assert restored.town_coffers_total == 1000
    assert counts(restored.slots) == counts(state.slots)


def test_format_upgrade_retains_permanent_rollback_copy_and_old_build_refuses_it(game,monkeypatch,tmp_path):
    import json

    from steam_client import storage
    slots = [game.build_default_slot_payload() for _ in range(3)]
    path = tmp_path/'chronicles.json'
    original = json.dumps({'format_version':2,'checksum':AtomicSaveStore._checksum(slots),'slots':slots}).encode()
    path.write_bytes(original)
    store = AtomicSaveStore(path)
    store.load()
    store.save(slots)
    backup = next(store.backups.glob('before-format-3-from-2-*.json'))
    assert backup.read_bytes() == original
    for number in range(14):
        slots[0]['carryover_gold'] = number
        store.save(slots)
    assert backup.read_bytes() == original
    upgraded = path.read_bytes()
    monkeypatch.setattr(storage,'CURRENT_SAVE_VERSION',2)
    with pytest.raises(UnsupportedSaveVersion):
        AtomicSaveStore(path).load()
    assert path.read_bytes() == upgraded


def test_local_reset_never_strands_guild_members_or_deletes_escrow(game,monkeypatch):
    state,town = fixture(game,monkeypatch)
    listing = town.post(state.player.inventory[0],123)
    charter = town.found('Quiet Lanterns','')
    previous = copy.deepcopy(state.slots[0])
    state.slots[0] = state.ladder_reset_slot_payload(2,1,previous)
    validate_slots(state.slots)
    data = state.slots[0]['town_services']
    assert data['guild_id'] == charter['id']
    assert data['listings'][0]['id'] == listing['id']
    assert data['listings'][0]['status'] == 'active'
    assert state.slots[0]['town_service_spend'] == {'guild_charter':1000}


def test_service_feedback_and_reviews_do_not_leak_into_another_scene(game,monkeypatch):
    _,town = fixture(game,monkeypatch)
    town.enter('bazaar')
    town.notice,town.error,town.receipt = 'Listing returned.',False,{'key':'receipt'}
    town.armed = {'operation':'post'}
    town.enter('bazaar')
    assert town.notice == 'Listing returned.' and town.armed is not None
    town.enter('guild')
    assert town.notice == '' and not town.error and town.receipt is None
    assert town.armed is None and town.selected is None
