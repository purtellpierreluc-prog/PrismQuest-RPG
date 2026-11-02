import copy
import random
from collections import deque
from unittest.mock import Mock

import pytest
from test_runtime_regressions import state_for

from steam_client import labyrinth as lab
from steam_client.transactions import DesktopTransactionError


def walk(graph,start):
    seen,queue = {start},deque([start])
    while queue:
        node = queue.popleft()
        for neighbor in graph[node]:
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return seen


@pytest.mark.parametrize('seed',range(40))
def test_maze_is_connected_reciprocal_bounded_and_has_actual_walls(seed):
    row = {'id':str(seed),'floor':1,'grid_size':7}
    graph = lab.passages(row)
    assert len(graph) == 49 and len(walk(graph,'3,3')) == 49
    edges = sum(len(neighbors) for neighbors in graph.values())//2
    assert 48 <= edges <= 54
    for key,neighbors in graph.items():
        x,y = map(int,key.split(','))
        for neighbor in neighbors:
            nx,ny = map(int,neighbor.split(','))
            assert abs(nx-x)+abs(ny-y) == 1 and key in graph[neighbor]
            assert 0 <= nx < 7 and 0 <= ny < 7
    assert graph == lab.passages(row)
    assert graph != lab.passages({**row,'floor':2})


def test_map_and_discovery_lookups_do_not_consume_combat_randomness():
    before = random.getstate()
    row = {'id':'independent-seed','floor':3,'grid_size':7}
    for key in lab.passages(row):
        lab.discovery_kind(row,key)
    assert random.getstate()==before


def expedition(game,monkeypatch):
    monkeypatch.setattr(game,'DESKTOP_MODE',True)
    state = state_for(game)
    assert state.create_labyrinth_solo_session() and state.labyrinth_start_floor()
    return state


def test_walls_reject_movement_without_advancing_or_awarding_anything(game,monkeypatch):
    state = expedition(game,monkeypatch)
    row = state.labyrinth_session_row
    graph = lab.passages(row)
    blocked = next((key,d) for key in graph for d,(dx,dy) in game.LABYRINTH_CONTROLLER_DIRECTIONS.items()
                   if (target:=f'{int(key.split(",")[0])+dx},{int(key.split(",")[1])+dy}') in graph and target not in graph[key])
    x,y = map(int,blocked[0].split(','))
    row['current_x'],row['current_y'] = x,y
    before,player = copy.deepcopy(row),state.player.to_dict()
    assert not state.labyrinth_move_party(blocked[1])
    assert state.labyrinth_session_row == before and state.player.to_dict() == player


def free_neighbor(state,game,event):
    row = state.labyrinth_session_row
    key = f'{row["current_x"]},{row["current_y"]}'
    target = lab.passages(row)[key][0]
    x,y = map(int,target.split(','))
    dx,dy = x-row['current_x'],y-row['current_y']
    row['tile_states'][target] = {'visited':False,'resolved':False,'kind':'free'}
    return target,next(d for d,delta in game.LABYRINTH_CONTROLLER_DIRECTIONS.items() if delta==(dx,dy))


@pytest.mark.parametrize('event',['hearth','tide','mirror','sanctuary','quiet'])
def test_discoveries_resolve_once_and_leave_combat_rewards_unchanged(game,monkeypatch,event):
    state = expedition(game,monkeypatch)
    monkeypatch.setattr(lab,'discovery_kind',lambda row,key:event)
    target,direction = free_neighbor(state,game,event)
    gold,xp,items = state.player.gold,state.player.xp,len(state.player.inventory)
    assert state.labyrinth_move_party(direction)
    assert state.labyrinth_session_row['tile_states'][target]['resolved']
    assert state.labyrinth_session_row['status'] == 'exploring'
    assert (state.player.gold,state.player.xp,len(state.player.inventory)) == (gold,xp,items)
    assert state.labyrinth_session_row['pending_encounter']['discovery']['kind'] == event
    checkpoint = copy.deepcopy(state.labyrinth_session_row)
    before = state.player.to_dict()
    reverse = {'up':'down','down':'up','left':'right','right':'left'}
    assert state.labyrinth_move_party(reverse[direction])
    assert state.labyrinth_move_party(direction)
    assert state.player.to_dict() == before
    assert state.labyrinth_session_row['tile_states'][target] == checkpoint['tile_states'][target]


def test_discovery_save_failure_restores_position_resources_and_unconsumed_tile(game,monkeypatch):
    state = expedition(game,monkeypatch)
    monkeypatch.setattr(lab,'discovery_kind',lambda row,key:'hearth')
    target,direction = free_neighbor(state,game,'hearth')
    before,player = copy.deepcopy(state.labyrinth_session_row),state.player.to_dict()
    state.persist_to_disk = Mock(side_effect=OSError('disk full'))
    with pytest.raises(DesktopTransactionError):
        state.labyrinth_move_party(direction)
    assert state.labyrinth_session_row == before and state.player.to_dict() == player
    assert not state.labyrinth_session_row['tile_states'][target]['visited']


def test_old_checkpoint_geometry_stays_stable_and_does_not_clear_progress(game,monkeypatch):
    state = expedition(game,monkeypatch)
    row = state.labyrinth_session_row
    row['tile_states']['0,0'] = {'kind':'free','visited':True,'resolved':True}
    state.sync_active_slot()
    restored = state_for(game)
    restored.slots = copy.deepcopy(state.slots)
    restored.open_slot(0)
    assert lab.passages(restored.labyrinth_session_row) == lab.passages(row)
    assert restored.labyrinth_session_row['tile_states']['0,0']['visited']


@pytest.mark.parametrize('kind,resource,fraction',[('hearth','hp',.12),('tide','mana',.18)])
def test_fonts_restore_real_bounded_party_resources_and_survive_reload(game,monkeypatch,kind,resource,fraction):
    state = expedition(game,monkeypatch)
    monkeypatch.setattr(lab,'discovery_kind',lambda row,key:kind)
    _,direction = free_neighbor(state,game,kind)
    entry = state.labyrinth_session_row['pending_encounter']['party_state'][game._labyrinth_member_identity(state)]
    field,maximum = ('current_hp','max_hp') if resource=='hp' else ('current_mana','max_mana')
    before = max(1,entry[maximum]//3)
    entry[field],entry['player_snapshot'][resource] = before,before
    setattr(state.player,resource,before)
    assert state.labyrinth_move_party(direction)
    expected = min(entry[maximum],before+max(1,int(entry[maximum]*fraction)))
    assert getattr(state.player,resource)==expected
    restored = state_for(game)
    restored.slots = copy.deepcopy(state.slots)
    restored.open_slot(0)
    assert getattr(restored.player,resource)==expected


def test_sanctuary_revives_one_fallen_companion_without_creating_items(game,monkeypatch):
    state = expedition(game,monkeypatch)
    assert state.labyrinth_hire_companion('Shadow Mage')
    row = state.labyrinth_session_row
    identity = next(entry['user_id'] for entry in state.labyrinth_member_rows if entry.get('is_companion'))
    entry = row['pending_encounter']['party_state'][identity]
    entry['current_hp'],entry['is_downed'],entry['player_snapshot']['hp'] = 0,True,0
    monkeypatch.setattr(lab,'discovery_kind',lambda row,key:'sanctuary')
    _,direction = free_neighbor(state,game,'sanctuary')
    items = len(state.player.inventory)
    assert state.labyrinth_move_party(direction)
    healed = state.labyrinth_session_row['pending_encounter']['party_state'][identity]
    assert not healed['is_downed'] and healed['current_hp']==max(1,int(healed['max_hp']*.15))
    assert len(state.player.inventory)==items


def test_mirror_scouting_does_not_explore_rooms_or_advance_extra_cooldowns(game,monkeypatch):
    state = expedition(game,monkeypatch)
    monkeypatch.setattr(lab,'discovery_kind',lambda row,key:'mirror')
    _,direction = free_neighbor(state,game,'mirror')
    progress = game._labyrinth_progress_counter(state.labyrinth_session_row)
    assert state.labyrinth_move_party(direction)
    row = state.labyrinth_session_row
    assert sum(tile.get('scouted',False) for tile in row['tile_states'].values())==3
    assert sum(tile.get('visited',False) for tile in row['tile_states'].values())==2
    assert game._labyrinth_progress_counter(row)==progress+1
    assert game._labyrinth_normalize_session_row(row)['tile_states']==row['tile_states']
