"""Create disposable level-45 layout fixtures, never a normal player profile."""

import argparse
import copy
import logging
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from steam_client.paths import DesktopPaths
from steam_client.runtime import load_game
from steam_client.storage import AtomicSaveStore

parser = argparse.ArgumentParser()
parser.add_argument('directory')
parser.add_argument('--visual-cues', action='store_true', help='Include multiple item families and protected tier marks for UI checks.')
parser.add_argument('--well-audit', action='store_true', help='Disposable overpowered hero for quick real-engine Well settlement checks.')
parser.add_argument('--level', type=int, choices=[45,60], default=45, help='Use level 60 for Prismatic Quest acceptance checks.')
parser.add_argument('--town-audit', action='store_true', help='Normal damaged Warlock and a chain for Inn/town acceptance checks.')
parser.add_argument('--labyrinth-scene', choices=['boss','swarm','reward','defeated','lobby'], help='Disposable SSF scene fixture for Labyrinth layout acceptance only.')
parser.add_argument('--insight-audit',action='store_true',help='Disposable stat points, proficiency and class PQ history for hover/filter checks.')
args = parser.parse_args()
directory = Path(args.directory).resolve()
if not directory.is_relative_to(ROOT / '.local-test'):
    raise SystemExit('Fixtures must be inside SteamEdition/.local-test.')
if (directory / 'saves' / 'chronicles.json').exists():
    raise SystemExit('Refusing to replace an existing test save.')
os.environ['PRISMQUEST_DESKTOP'] = '1'
os.environ['PRISMQUEST_DATA_DIR'] = str(directory)
os.environ['NICEGUI_STORAGE_PATH'] = str(directory / 'ui')
paths = DesktopPaths.from_environment()
paths.prepare()
game = load_game(paths)
logging.getLogger('prismquest.runtime').disabled = True
slots = [game.build_default_slot_payload() for _ in range(3)]
for index, slot in enumerate(slots):
    player = game._labyrinth_build_companion_player('Warlock' if args.town_audit and index == 0 else 'Black Guard', args.level)
    player.name = 'Desktop Veteran'
    player.gold = 20000
    if args.town_audit and index == 0:
        player.hp = max(1,int(player.max_hp*.08))
        player.mana = 0
    if args.well_audit and index == 0:
        player.base_max_hp = 100000
        player.base_attack_min = 100000
        player.base_attack_max = 100001
        player.base_accuracy = 1.5
        player.unspent_stat_points = 12
        player.recalculate_stats()
        player.hp = player.max_hp
    player.inventory = [game.generate_specific_item(45, 'weapon', 'Axe', rarity) for rarity in ['Common', 'Fine', 'Rare', 'Epic', 'Relic'] for _ in range(6)]
    slot.update(player=player.to_dict(), town_tutorial_seen=True, guided_intro_stage=game.GUIDED_INTRO_COMPLETE,
                scene_tutorials_seen={key: True for key in slot['scene_tutorials_seen']},
                guided_discord_prompt_seen=True, first_death_inn_tutorial_seen=True, vault_capacity=30)
    slot['vault_items'] = [item.to_dict() for item in player.inventory[:15]]
    if args.town_audit and index == 0:
        slot['monster_chain_combo'] = 12
    if args.visual_cues and index == 0:
        families = [('weapon', 'Axe'), ('weapon', 'Dagger'), ('weapon', 'Staff'),
                    ('armor', 'Light'), ('armor', 'Medium'), ('armor', 'Heavy'),
                    ('charm', 'Fire'), ('charm', 'Ice'), ('charm', 'Lightning')]
        slot['player']['inventory'] = [game.generate_specific_item(45, family, subtype, rarity).to_dict()
                                       for family, subtype in families for rarity in ('Common', 'Rare', 'Epic')]
        for n, (family, subtype) in enumerate(families):
            tier = game.ITEM_BUCKETS[n]
            item = game.generate_specific_item(tier, family, subtype, 'Epic' if n % 2 else 'Rare')
            slot['saved_item_sets'][game.get_saved_item_category(item)] = {str(tier): item.to_dict()}
    if args.insight_audit and index == 0:
        slot['player']['unspent_stat_points'] = 3
        slot['player']['proficiency_levels']['Axe'] = 7
        slot['player']['proficiency_progress']['Axe'] = 23
        slot['pq_ledger_entries'] = [game.normalize_pq_ledger_entry({
            'id':f'fixture-{hero}','character_name':'Earlier Hero','player_class':hero,'level':60,'mode':'Core',
            'slot_index':1,'season_id':1,'passed':True,'elapsed_seconds':seconds,
            'completed_at':game._labyrinth_now_iso(),
        }) for hero,seconds in [('Black Guard',90),('Shadow Mage',30)]]
store = AtomicSaveStore(paths.save_file, paths.backups)
store.save(slots)
state = game.SessionState()
state.persist_runtime_session = lambda: None
state.persist_to_disk = lambda **_kwargs: None
for index in (1, 2):
    state.open_slot(index)
    assert state.create_labyrinth_solo_session()
    for companion in ['Shadow Mage', 'Night Angel', 'Night Assassin', 'Prismatic Templar']:
        assert state.labyrinth_hire_companion(companion)
    assert state.labyrinth_start_floor()
    if index == 1 and args.labyrinth_scene:
        row = copy.deepcopy(state.labyrinth_session_row)
        row['status'] = 'encounter' if args.labyrinth_scene=='swarm' else args.labyrinth_scene
        if args.labyrinth_scene in {'boss','swarm'}:
            boss = args.labyrinth_scene=='boss'
            row['pending_encounter'] = game._labyrinth_build_shared_encounter(state,row,state.labyrinth_member_rows,'Lamia' if boss else 'Bandit',args.level,boss=boss,tile_key='0,0')
            row['pending_encounter']['next_step_at'] = (datetime.now(UTC)+timedelta(minutes=5)).isoformat()
        elif args.labyrinth_scene=='reward':
            row['reward_options'] = game._labyrinth_build_reward_choices(1)
            # Freeze only these disposable layout fixtures; real combat/vote timers are untouched.
            row['pending_encounter'].update(reward_vote_started_at=(datetime.now(UTC)+timedelta(minutes=5)).isoformat(),reward_gold_gain=125)
        game._labyrinth_apply_local_session_update(state,row)
    if index == 2:
        row = copy.deepcopy(state.labyrinth_session_row)
        row['status'] = 'encounter'
        row['pending_encounter'] = game._labyrinth_build_shared_encounter(
            state, row, state.labyrinth_member_rows, game._labyrinth_choose_template(False), 45, boss=False, tile_key='0,0',
        )
        game._labyrinth_apply_local_session_update(state, row)
    state.sync_active_slot()
store.save(state.slots)
print(f'Disposable desktop test profile created: {directory}')
