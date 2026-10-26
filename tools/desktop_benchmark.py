"""Accelerated backend combat/save benchmark, not a real-time/UI soak test."""

import argparse
import copy
import json
import logging
import os
import random
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from steam_client.paths import DesktopPaths
from steam_client.runtime import load_game


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rounds', type=int, default=1000)
    parser.add_argument('--directory', default='.local-test/benchmark-03')
    parser.add_argument('--trace-memory', action='store_true', help='Enable allocation tracing; significantly increases CPU cost.')
    args = parser.parse_args()
    directory = Path(args.directory).resolve()
    if not directory.is_relative_to(ROOT / '.local-test') or directory.exists():
        raise SystemExit('Use a fresh directory under SteamEdition/.local-test.')
    if not 1 <= args.rounds <= 100000:
        raise SystemExit('Rounds must be between 1 and 100000.')
    os.environ.update(PRISMQUEST_DESKTOP='1', PRISMQUEST_DATA_DIR=str(directory), NICEGUI_STORAGE_PATH=str(directory / 'ui'), SUPABASE_URL='', SUPABASE_PUBLISHABLE_KEY='')
    paths = DesktopPaths.from_environment()
    paths.prepare()
    game = load_game(paths)
    logging.disable(logging.WARNING)
    random.seed(20261026)
    state = game.SessionState()
    state.persist_runtime_session = lambda: None
    state.active_slot_index = 0
    state.player = game._labyrinth_build_companion_player('Black Guard', 45)
    state.player.gold = 20000
    state.player.inventory = [game.generate_specific_item(45, 'weapon', 'Axe', 'Rare') for _ in range(100)]
    state.guided_intro_stage = game.GUIDED_INTRO_COMPLETE
    state.screen, state.game_tab = 'game', 'labyrinth'
    assert state.create_labyrinth_solo_session()
    for companion in ['Night Angel', 'Warlock', 'Prismatic Templar', 'Shadow Mage']:
        assert state.labyrinth_hire_companion(companion)
    assert state.labyrinth_start_floor()
    times = []
    encounters = 0
    if args.trace_memory:
        tracemalloc.start()
    started, cpu_started = time.perf_counter(), time.process_time()
    for index in range(args.rounds):
        if state.labyrinth_session_row.get('status') not in {'encounter', 'boss'}:
            encounters += 1
            row = copy.deepcopy(state.labyrinth_session_row)
            row['status'] = 'encounter'
            row['pending_encounter'] = game._labyrinth_build_shared_encounter(state, row, state.labyrinth_member_rows, game._labyrinth_choose_template(False), 45, boss=False, tile_key='0,0')
            game._labyrinth_apply_local_session_update(state, row)
        start = time.perf_counter()
        assert state.run_labyrinth_encounter(ignore_timing=True)
        times.append((time.perf_counter() - start) * 1000)
        if state.labyrinth_session_row.get('status') == 'defeated':
            assert state.labyrinth_reset_after_defeat()
            if state.labyrinth_session_row.get('status') == 'lobby':
                assert state.labyrinth_start_floor()
        if index % 100 == 0:
            print(f'{index}/{args.rounds} rounds', flush=True)
    state.sync_active_slot()
    snapshot = copy.deepcopy(state.slots)
    store = game.DESKTOP_SAVE_STORE
    for _ in range(100):
        assert store.save(snapshot) is False
    current, peak = tracemalloc.get_traced_memory() if args.trace_memory else (None, None)
    if args.trace_memory:
        tracemalloc.stop()
    assert store.load() == snapshot
    report = {
        'kind': 'accelerated-backend-only', 'rounds': args.rounds, 'encounters': encounters,
        'party_size': 5, 'inventory_items': 100, 'wall_seconds': time.perf_counter() - started,
        'cpu_seconds': time.process_time() - cpu_started,
        'round_ms': {'median': statistics.median(times), 'p95': sorted(times)[int((len(times) - 1) * .95)], 'maximum': max(times)},
        'traced_python_memory': {'current_bytes': current, 'peak_bytes': peak},
        'save_metrics': store.metrics,
        'memory_tracing_enabled': args.trace_memory,
        'limitations': 'Optional tracemalloc adds overhead. No rendering, real-time pacing, network or multi-hour soak claim. Not a gameplay balance test.',
    }
    (directory / 'benchmark.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
