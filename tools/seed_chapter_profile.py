"""Seed level-60 chapter QA fixtures only under the ignored .local-test directory."""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from steam_client.paths import DesktopPaths
from steam_client.runtime import load_game
from steam_client.storage import AtomicSaveStore


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--final',action='store_true')
    args=parser.parse_args()
    directory=args.directory.resolve()
    if not directory.is_relative_to(ROOT/'.local-test') or (directory/'saves/chronicles.json').exists():
        raise SystemExit('Use a new disposable .local-test directory.')
    os.environ.update(PRISMQUEST_DESKTOP='1',PRISMQUEST_DATA_DIR=str(directory),NICEGUI_STORAGE_PATH=str(directory/'ui'))
    paths=DesktopPaths.from_environment()
    paths.prepare()
    g=load_game(paths)
    slots=[g.build_default_slot_payload() for _ in range(3)]
    for index,slot in enumerate(slots):
        p=g._labyrinth_build_companion_player('Prismatic Sorceress' if args.final and index==0 else 'Black Guard',60)
        p.name='Prism Veteran'
        p.gold=20000
        p.inventory=[g.generate_specific_item(45,'weapon','Axe',r) for r in ['Fine','Rare','Epic']]
        slot.update(player=p.to_dict(),town_tutorial_seen=True,guided_intro_stage=g.GUIDED_INTRO_COMPLETE,
                    scene_tutorials_seen={k:True for k in slot['scene_tutorials_seen']},guided_discord_prompt_seen=True,
                    first_death_inn_tutorial_seen=True,vault_capacity=20)
        slot['vault_items']=[g.generate_specific_item(40,'armor','Heavy','Epic').to_dict()]
    AtomicSaveStore(paths.save_file,paths.backups).save(slots)
    print('Created disposable level-60 chapter fixture.')


if __name__=='__main__':
    main()
