import copy
import random
from unittest.mock import Mock, patch

import pytest
from test_runtime_regressions import start_encounter, state_for


@pytest.mark.parametrize('size,roll,count',[(1,.25,2),(2,.25,2),(2,.75,4),(3,.25,4),(4,.25,4),(4,.75,6),(5,.25,6)])
def test_desktop_normal_packs_double_but_guardian_stays_singular(game,monkeypatch,size,roll,count):
    monkeypatch.setattr(game,'DESKTOP_MODE',True)
    monkeypatch.setattr(game.random,'random',lambda:roll)
    assert game._labyrinth_encounter_monster_count(size)==count
    assert game._labyrinth_encounter_monster_count(size,boss=True)==1


def test_desktop_swarm_halves_power_not_hit_consistency_or_boss_stats(game,monkeypatch):
    seed = random.getstate()
    monkeypatch.setattr(game,'DESKTOP_MODE',False)
    original,_ = game._generate_labyrinth_monster('Bandit',45,floor=3)
    random.setstate(seed)
    monkeypatch.setattr(game,'DESKTOP_MODE',True)
    swarm,_ = game._generate_labyrinth_monster('Bandit',45,floor=3)
    for field in ['max_hp','physical_armor','magic_resistance','attack_min','attack_max']:
        assert getattr(swarm,field)==round(getattr(original,field)*.5)
    assert swarm.hp==swarm.max_hp
    assert swarm.accuracy==original.accuracy and swarm.crit_chance==original.crit_chance
    random.setstate(seed)
    boss,_ = game._generate_labyrinth_monster('Lamia',45,boss=True)
    random.setstate(seed)
    monkeypatch.setattr(game,'DESKTOP_MODE',False)
    old_boss,_ = game._generate_labyrinth_monster('Lamia',45,boss=True)
    assert boss==old_boss


def test_new_desktop_tiles_have_40_percent_encounter_threshold_without_rerolling_existing(game,monkeypatch):
    monkeypatch.setattr(game,'DESKTOP_MODE',True)
    monkeypatch.setattr(game.hashlib,'sha1',lambda *args:Mock(hexdigest=lambda:'00000027'+'0'*32))
    assert game._labyrinth_tile_kind_for_coords({'id':'rate'},0,0)=='encounter'
    monkeypatch.setattr(game.hashlib,'sha1',lambda *args:Mock(hexdigest=lambda:'00000028'+'0'*32))
    assert game._labyrinth_tile_kind_for_coords({'id':'rate'},0,0)=='free'
    old = {'0,0':{'kind':'encounter','visited':True,'resolved':True}}
    assert game._labyrinth_complete_tile_states(old,7,{'id':'rate'})['0,0']['kind']=='encounter'


def test_every_party_and_monster_actor_resolves_in_one_round_update(game,monkeypatch):
    monkeypatch.setattr(game,'DESKTOP_MODE',True)
    state = state_for(game)
    assert state.create_labyrinth_solo_session()
    for hero in ['Shadow Mage','Night Angel','Night Assassin','Prismatic Templar']:
        assert state.labyrinth_hire_companion(hero)
    assert state.labyrinth_start_floor()
    row = dict(state.labyrinth_session_row)
    row['status'] = 'encounter'
    row['pending_encounter'] = game._labyrinth_build_shared_encounter(state,row,state.labyrinth_member_rows,'Bandit',45,boss=False,tile_key='0,0')
    for monster in row['pending_encounter']['monster_snapshots']:
        monster.update(hp=100000000,max_hp=100000000,attack_min=1,attack_max=2)
    game._labyrinth_apply_local_session_update(state,row)
    with patch.object(game,'_labyrinth_resolve_turn',wraps=game._labyrinth_resolve_turn) as turns:
        assert state.run_labyrinth_encounter(ignore_timing=True)
    assert turns.call_count==11
    assert state.labyrinth_session_row['pending_encounter']['round']==2
    assert state.labyrinth_session_row['pending_encounter']['turn_index']==0
    state.log_delay_ms = 1000
    assert game._labyrinth_step_delay_seconds(state)==1.0
    state.labyrinth_slow_cadence_mode = True
    assert game._labyrinth_step_delay_seconds(state)>=2.25


def test_same_step_cannot_repeat_a_batched_round(game,monkeypatch):
    monkeypatch.setattr(game,'DESKTOP_MODE',True)
    state = state_for(game)
    pending = start_encounter(game,state)
    step = (state.labyrinth_session_row['id'],pending['started_at'],pending['sequence'])
    assert state.run_labyrinth_encounter(ignore_timing=True,expected_step=step)
    before = copy.deepcopy(state.labyrinth_session_row)
    assert not state.run_labyrinth_encounter(ignore_timing=True,expected_step=step)
    assert state.labyrinth_session_row==before


def test_compact_inspection_reports_exact_stats_and_current_proficiency_progress(game):
    from steam_client.arena_inspection import combat_html, proficiency_html
    player = state_for(game).player
    player.weapon_attack_min,player.weapon_attack_max = 555,1199
    player.proficiency_levels['Axe'],player.proficiency_progress['Axe'] = 7,23
    before = player.to_dict()
    stats,profs = combat_html(player),proficiency_html(player,game)
    assert '555-1,199' in stats and 'Evade' in stats
    assert 'Lv 7' in profs and f'23 / {game.proficiency_threshold_for_level(7):,}' in profs
    assert 'Each level' not in profs and 'successful player hit' not in profs
    assert player.to_dict()==before


def test_ladder_class_filter_uses_only_successful_matching_class_history(game,monkeypatch):
    from steam_client.community import town_for
    monkeypatch.setattr(game,'DESKTOP_MODE',True)
    state = state_for(game,'Shadow Mage')
    state.slots[0]['pq_ledger_entries'] = [
        {'player_class':'Black Guard','passed':True,'elapsed_seconds':120,'character_name':'Earlier Hero'},
        {'player_class':'Black Guard','passed':True,'elapsed_seconds':90,'character_name':'Earlier Hero'},
        {'player_class':'Black Guard','passed':False,'elapsed_seconds':1},
        {'player_class':'Shadow Mage','passed':True,'elapsed_seconds':20},
    ]
    town = town_for(state,game)
    before = copy.deepcopy(state.slots)
    filtered = town.ladder('Black Guard')
    assert len(filtered)==1 and filtered[0]['fastest']==90
    assert filtered[0]['class']=='Black Guard' and filtered[0]['current_class']=='Shadow Mage'
    assert filtered[0]['level']==state.player.level and filtered[0]['pq_name']=='Earlier Hero'
    assert not town.ladder('Warlock')
    assert town.ladder()[0]['fastest']==20
    assert state.slots==before


def test_volley_popups_sum_hits_instead_of_overwriting_earlier_allies(game):
    from steam_client.swarm import volley_popup
    popups = {}
    volley_popup(game,popups,'monster-0',10,False,enabled=True)
    volley_popup(game,popups,'monster-0',25,True,enabled=True)
    assert popups['monster-0']['amount']==35 and popups['monster-0']['hits']==2
    assert popups['monster-0']['crit']
    volley_popup(game,popups,'monster-0',99,True,enabled=False)
    assert popups['monster-0']['amount']==35


def test_class_filter_retains_recorded_legacy_class_bests_without_inventing_attempts(game,monkeypatch):
    from steam_client.community import town_for
    monkeypatch.setattr(game,'DESKTOP_MODE',True)
    state = state_for(game,'Shadow Mage')
    state.ladder_stats['Black Guard']['fastest_masterquest_seconds'] = 123
    state.slots[0]['pq_ledger_entries'] = []
    before = copy.deepcopy(state.ladder_stats)
    rows = town_for(state,game).ladder('Black Guard')
    assert len(rows)==1 and rows[0]['fastest']==123
    assert rows[0]['attempts']==0 and state.ladder_stats==before
