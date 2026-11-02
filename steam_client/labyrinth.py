"""Cached connected mazes and first-visit discoveries over the real Lab engine."""

import copy
import hashlib
import random
from collections import deque
from functools import lru_cache

from .chapters import atomic_progress

DIRECTIONS = {'up':(0,-1),'right':(1,0),'down':(0,1),'left':(-1,0)}
DISCOVERIES = {
    'quiet':('Still Light','A quiet passage. Your cleared route stays safe.'),
    'hearth':('The Living Font','Restore 12% max health to each standing ally.'),
    'tide':('Aether Well','Restore 18% max mana to each standing ally.'),
    'mirror':('The Cartographer\'s Mirror','Reveal three nearby unexplored rooms without entering them.'),
    'sanctuary':('Sanctuary of Echoes','Return one fallen ally at 15% health; otherwise restore 6% health to the standing party.'),
}


def _basis(row):
    return f"maze-v1|{row.get('id','')}|{row.get('join_code','')}|{row.get('floor',1)}|{row.get('grid_size',7)}"


@lru_cache(maxsize=128)
def _carve(seed,size):
    rng = random.Random(int(hashlib.sha256(seed.encode()).hexdigest(),16))
    graph = {f'{x},{y}':set() for y in range(size) for x in range(size)}
    start = f'{size//2},{size//2}'
    stack,seen = [start],{start}
    while stack:
        key = stack[-1]
        x,y = map(int,key.split(','))
        options = [f'{x+dx},{y+dy}' for dx,dy in DIRECTIONS.values()
                   if f'{x+dx},{y+dy}' in graph and f'{x+dx},{y+dy}' not in seen]
        if not options:
            stack.pop()
            continue
        neighbor = rng.choice(options)
        graph[key].add(neighbor)
        graph[neighbor].add(key)
        stack.append(neighbor)
        seen.add(neighbor)
    # A handful of loops make choices meaningful without turning it into an open grid.
    dead_ends = [key for key in graph if len(graph[key])==1]
    rng.shuffle(dead_ends)
    for key in dead_ends[:4]:
        x,y = map(int,key.split(','))
        options = [f'{x+dx},{y+dy}' for dx,dy in DIRECTIONS.values()
                   if f'{x+dx},{y+dy}' in graph and f'{x+dx},{y+dy}' not in graph[key]]
        if options:
            neighbor = rng.choice(options)
            graph[key].add(neighbor)
            graph[neighbor].add(key)
    return tuple((key,tuple(sorted(neighbors))) for key,neighbors in graph.items())


def passages(row):
    size = max(3,min(15,int(row.get('grid_size',7))))
    return dict(_carve(_basis(row),size))


def allows(row,direction):
    if direction not in DIRECTIONS:
        return False
    x,y = int(row.get('current_x',3)),int(row.get('current_y',3))
    dx,dy = DIRECTIONS[direction]
    return f'{x+dx},{y+dy}' in passages(row).get(f'{x},{y}',())


def discovery_kind(row,key):
    roll = int(hashlib.sha256(f'{_basis(row)}|discovery|{key}'.encode()).hexdigest()[:8],16)%100
    return 'quiet' if roll<60 else 'hearth' if roll<74 else 'tide' if roll<88 else 'mirror' if roll<96 else 'sanctuary'


def preserve_discovery(row,data):
    previous = row.get('pending_encounter',{})
    for key in ('discovery','discovery_log'):
        if key not in data and key in previous:
            data[key] = previous[key]
    return data


def discover(game,row,party,tiles,key):
    kind = discovery_kind(row,key)
    title,description = DISCOVERIES[kind]
    party = copy.deepcopy(party)
    effects = game._labyrinth_effect_totals_for_session(row)
    health,mana,revived = 0,0,''
    fallen = next((identity for identity,entry in party.items() if entry.get('is_downed') or entry.get('current_hp',0)<=0),None)
    if kind in {'hearth','tide','sanctuary'}:
        for identity,entry in list(party.items()):
            is_fallen = bool(entry.get('is_downed') or entry.get('current_hp',0)<=0)
            if is_fallen and not (kind=='sanctuary' and identity==fallen):
                continue
            if kind=='sanctuary' and fallen and identity!=fallen:
                continue
            player = game._labyrinth_member_player_from_entry(entry,effects,party,row)
            old_hp,old_mana = player.hp,player.mana
            if kind=='tide':
                player.mana = min(player.max_mana,player.mana+max(1,int(player.max_mana*.18)))
            else:
                fraction = .12 if kind=='hearth' else .15 if is_fallen else .06
                factor = max(.10,float(getattr(player,'labyrinth_healing_factor',1)))
                amount = max(1,int(player.max_hp*fraction*factor))
                player.hp = min(player.max_hp,amount if is_fallen else player.hp+amount)
                if is_fallen:
                    revived = str(entry.get('character_name') or player.name)
            health += max(0,player.hp-old_hp)
            mana += max(0,player.mana-old_mana)
            party[identity] = game._labyrinth_store_entry_from_player(entry,player)
    elif kind=='mirror':
        graph,seen,queue = passages(row),{key},deque([key])
        revealed = 0
        while queue and revealed<3:
            current = queue.popleft()
            for neighbor in graph[current]:
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                queue.append(neighbor)
                tile = tiles[neighbor]
                if not tile.get('visited') and not tile.get('scouted') and revealed<3:
                    tiles[neighbor] = {**tile,'scouted':True}
                    revealed += 1
        description = f'{revealed} room'+('s' if revealed!=1 else '')+' revealed. Exploring them is still your choice.'
    if kind in {'hearth','tide','sanctuary'}:
        description = (f'{revived} returns. ' if revived else '')+(f'+{mana:,} mana across the party.' if kind=='tide' else f'+{health:,} health across the party.')
        if not health and not mana:
            description = 'Your standing party is already replenished. The light asks for nothing.'
    record = {'id':f'{row["id"]}:{row["floor"]}:{key}','kind':kind,'title':title,'detail':description,
              'floor':row['floor'],'tile':key,'health':health,'mana':mana}
    pending = game._labyrinth_pending_payload(row,{'party_state':party,'discovery':record})
    journal = list(pending.get('discovery_log',[]))
    if kind!='quiet':
        journal.insert(0,record)
    pending['discovery_log'] = journal[:60]
    row['pending_encounter'] = pending
    return party


def travel(state,game,direction,action):
    row = state.labyrinth_session_row
    if not row or row.get('status')!='exploring' or not allows(row,direction) or not state.labyrinth_is_controller():
        return action()
    dx,dy = DIRECTIONS[direction]
    target = f'{row["current_x"]+dx},{row["current_y"]+dy}'
    if row.get('tile_states',{}).get(target,{}).get('visited'):
        return action()
    # First visits and their effects form one durable checkpoint; failed writes undo both.
    snapshot = copy.deepcopy({key:value for key,value in state.__dict__.items() if key.startswith('labyrinth_')})
    def commit():
        state._desktop_maze_transaction = True
        try:
            result = action()
            if result:
                state.sync_active_slot()
            return result
        finally:
            state._desktop_maze_transaction = False
    try:
        return atomic_progress(state,commit,failure_message='The expedition step could not be saved. Position, discoveries and resources were restored. Check storage and retry.')
    except Exception:
        for key,value in snapshot.items():
            state.__dict__[key] = value
        raise
