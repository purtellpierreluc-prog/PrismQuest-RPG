import copy
from unittest.mock import Mock

import pytest
from test_runtime_regressions import state_for

from steam_client.hearth import HearthError, forecast, hearth_for
from steam_client.transactions import DesktopTransactionError


def test_town_spending_is_in_chronicle_payload_and_survives_reopening(game,monkeypatch):
    monkeypatch.setattr(game,'DESKTOP_MODE',True)
    state = state_for(game)
    state.record_town_service_spend('inn',3)
    state.record_town_service_spend('vault',100)
    state.sync_active_slot()
    assert state.slots[0]['town_service_spend'] == {'inn':3,'vault':100}
    restored = game.SessionState()
    restored.persist_to_disk = Mock()
    restored.persist_runtime_session = Mock()
    restored.slots = copy.deepcopy(state.slots)
    restored.open_slot(0)
    assert restored.town_coffers_total == 103
    assert restored.local_town_service_spend == {'inn':3,'vault':100}


def test_town_spending_does_not_bleed_between_chronicles_or_double_on_load(game,monkeypatch):
    monkeypatch.setattr(game,'DESKTOP_MODE',True)
    state = state_for(game)
    state.record_town_service_spend('marketplace',120)
    state.sync_active_slot()
    state.open_slot(1)
    assert state.town_coffers_total == 0
    state.record_town_service_spend('vault',100)
    state.sync_active_slot()
    state.open_slot(0)
    state.open_slot(0)
    assert state.town_coffers_total == 120
    assert state.slots[1]['town_service_spend'] == {'vault':100}


def test_legacy_chronicle_initializes_empty_persistent_coffers(game):
    raw = game.build_default_slot_payload()
    raw.pop('town_service_spend',None)
    assert game.normalize_slot_payload(raw)['town_service_spend'] == {}


def test_cannot_guess_or_backfill_historical_spending(game,monkeypatch):
    monkeypatch.setattr(game,'DESKTOP_MODE',True)
    state = state_for(game)
    state.player.gold = 8000
    state.sync_active_slot()
    assert state.slots[0]['town_service_spend'] == {}
    assert 'during this visit' not in state.town_crier_status_text()


def test_failed_rest_restores_resources_gold_chain_and_coffers(game,monkeypatch):
    monkeypatch.setattr(game,'DESKTOP_MODE',True)
    state = state_for(game,'Warlock')
    state.player.hp = 1
    state.player.mana = 0
    state.monster_chain_combo = 17
    before = copy.deepcopy(state.player.to_dict())
    state.persist_to_disk = Mock(side_effect=OSError('disk full'))
    with pytest.raises(DesktopTransactionError):
        state.inn_rest()
    assert state.player.to_dict() == before
    assert state.monster_chain_combo == 17
    assert state.local_town_service_spend == {}


def test_normalization_preserves_coffers_across_pq_ledger_updates(game):
    slot = game.build_default_slot_payload()
    slot['town_service_spend'] = {'inn':7,'well':20}
    assert game.normalize_slot_payload(slot)['town_service_spend'] == slot['town_service_spend']


@pytest.mark.parametrize('hero',['Black Guard','Shadow Mage','Warlock','Ember Fae','Prismatic Sorceress'])
def test_room_forecast_matches_original_rest_and_spends_no_gold_itself(game,monkeypatch,hero):
    monkeypatch.setattr(game,'DESKTOP_MODE',True)
    state = state_for(game,hero)
    state.player.hp,state.player.mana = 1,0
    before = copy.deepcopy(state.player.to_dict())
    view = forecast(state,game)
    assert state.player.to_dict() == before
    receipt = hearth_for(state,game).rest()
    assert (state.player.hp,state.player.mana) == (view.hp_after,view.mana_after)
    assert receipt.health == view.hp_after-view.hp_before
    assert receipt.mana == view.mana_after-view.mana_before
    assert state.player.gold == before['gold']-game.inn_rest_cost(hero)
    assert state.town_coffers_total == view.cost


def test_chain_requires_explicit_confirmation_and_receipt_is_not_a_second_charge(game,monkeypatch):
    monkeypatch.setattr(game,'DESKTOP_MODE',True)
    state = state_for(game,'Warlock')
    state.player.hp = 1
    state.monster_chain_combo = 12
    inn = hearth_for(state,game)
    before = state.player.to_dict()
    assert inn.rest() is None and state.player.to_dict() == before
    receipt = inn.rest()
    assert receipt.chain == 12 and state.monster_chain_combo == 0
    assert state.player.gold == before['gold']-receipt.cost


def test_full_resources_and_no_chain_do_not_waste_gold(game,monkeypatch):
    monkeypatch.setattr(game,'DESKTOP_MODE',True)
    state = state_for(game,'Warlock')
    state.player.hp,state.player.mana = state.player.max_hp,state.player.max_mana
    before = state.player.to_dict()
    with pytest.raises(HearthError):
        hearth_for(state,game).rest()
    assert state.player.to_dict() == before
