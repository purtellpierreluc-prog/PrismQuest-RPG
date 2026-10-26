"""Create disposable level-45 layout fixtures, never a normal player profile."""

import argparse
import copy
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from steam_client.paths import DesktopPaths
from steam_client.runtime import load_game
from steam_client.storage import AtomicSaveStore

parser = argparse.ArgumentParser()
parser.add_argument('directory')
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
    player = game._labyrinth_build_companion_player('Black Guard', 45)
    player.name = 'Desktop Veteran'
    player.gold = 20000
    player.inventory = [game.generate_specific_item(45, 'weapon', 'Axe', rarity) for rarity in ['Common', 'Fine', 'Rare', 'Epic', 'Relic'] for _ in range(6)]
    slot.update(player=player.to_dict(), town_tutorial_seen=True, guided_intro_stage=game.GUIDED_INTRO_COMPLETE,
                scene_tutorials_seen={key: True for key in slot['scene_tutorials_seen']},
                guided_discord_prompt_seen=True, first_death_inn_tutorial_seen=True, vault_capacity=30)
    slot['vault_items'] = [item.to_dict() for item in player.inventory[:15]]
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
