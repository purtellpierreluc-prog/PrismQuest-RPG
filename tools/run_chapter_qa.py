"""Source-only test harness; writes the oracle to a local fixture, never the UI.

Not imported, packaged or enabled by the game. Real puzzle rolls are observed,
not replaced, so scripted outcomes can exercise the original settlement safely.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from steam_client import runtime


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--port',type=int,required=True)
    args=parser.parse_args()
    directory=args.data_dir.resolve()
    if not directory.is_relative_to(ROOT/'.local-test'):
        raise SystemExit('The source-only oracle requires a disposable .local-test profile.')
    original_load=runtime.load_game
    def observed_load(paths):
        g=original_load(paths)
        original=g.SessionState.ensure_masterquest_scene_state
        last=None
        def observed(state,new_visit=False):
            nonlocal last
            original(state,new_visit)
            payload={'solution':state.masterquest_solution,'lights':state.masterquest_essence_order}
            value=json.dumps(payload,sort_keys=True)
            if payload['solution'] and value!=last:
                (directory/'qa-oracle.json').write_text(value,encoding='utf-8')
                last=value
        g.SessionState.ensure_masterquest_scene_state=observed
        return g
    runtime.load_game=observed_load
    runtime.launch(['--browser','--port',str(args.port),'--data-dir',str(directory)])


if __name__=='__main__':
    main()
