import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

from steam_client.experience import (
    ITEM_TYPE_COLORS,
    item_visual_style,
    monster_defense_cue,
    saved_archive_marks,
)


def test_type_frame_and_rarity_wash_are_independent_and_read_only(game):
    dagger = game.generate_specific_item(25, 'weapon', 'Dagger', 'Epic')
    other_rarity = copy.deepcopy(dagger)
    other_rarity.rarity = 'Rare'
    axe = game.generate_specific_item(25, 'weapon', 'Axe', 'Epic')
    original = dagger.to_dict()
    style = item_visual_style(dagger, game)
    assert f'--pd-type:{ITEM_TYPE_COLORS["dagger"]}' in style
    assert f'--pd-rarity:{game.RARITY_COLORS["Epic"]}' in style
    assert style.split(';')[0] == item_visual_style(other_rarity, game).split(';')[0]
    assert style.split(';')[1] == item_visual_style(axe, game).split(';')[1]
    assert dagger.to_dict() == original
    assert len(set(ITEM_TYPE_COLORS.values())) == len(ITEM_TYPE_COLORS) == 9


def test_archive_distinguishes_empty_filtered_and_matching_marks_without_mutation(game):
    item = game.generate_specific_item(25, 'weapon', 'Dagger', 'Epic')
    hidden = game.generate_specific_item(45, 'weapon', 'Dagger', 'Rare')
    stored = {'dagger': {25: item, 45: hidden}}
    before = {tier: value.to_dict() for tier, value in stored['dagger'].items()}
    entries = [('saved', ('dagger', 25), item)]
    marks = saved_archive_marks('dagger', [45, 25, 1], entries, stored)
    assert marks[0].occupied and marks[0].item is None
    assert marks[1].occupied and marks[1].item is item
    assert not marks[2].occupied and marks[2].item is None
    assert {tier: value.to_dict() for tier, value in stored['dagger'].items()} == before


@pytest.mark.parametrize('level', [1, 45, 80])
@pytest.mark.parametrize('kind,armor_mult,resist_mult', [('species', 1, 1), ('armor', 1.5, 1), ('ward', 1, 1.5), ('both', 1.5, 1.5)])
def test_monster_aura_uses_actual_level_adjusted_defenses(game, level, kind, armor_mult, resist_mult):
    scale = game.monster_late_game_scale(level)
    armor = max(1, round(level * scale))
    resist = max(1, round((2 + (level-1)//2) * scale))
    monster = SimpleNamespace(level=level, damage_school='magic', physical_armor=armor*armor_mult, magic_resistance=resist*resist_mult)
    original = vars(monster).copy()
    assert monster_defense_cue(monster, game.monster_late_game_scale).kind == kind
    assert vars(monster) == original


def test_unknown_opponent_does_not_claim_defensive_strength(game):
    cue = monster_defense_cue(None, game.monster_late_game_scale)
    assert cue.kind == 'none' and not cue.label


def test_shared_item_palette_does_not_suppress_existing_loot_bloom_animation():
    css = (Path(__file__).resolve().parents[1] / 'steam_client/static/experience.css').read_text()
    surface_rule = css.split('.mq-desktop .pd-item-surface,', 1)[1].split('}', 1)[0]
    assert 'box-shadow' not in surface_rule
    assert '@keyframes pd-find-bloom' in css and '@keyframes pd-find-light' in css


def test_protected_type_tier_mark_survives_prismatic_quest_and_next_run(game, monkeypatch):
    from test_runtime_regressions import state_for
    monkeypatch.setattr(game, 'DESKTOP_MODE', True)
    state = state_for(game)
    item = game.generate_specific_item(25, 'weapon', 'Dagger', 'Epic')
    state.saved_item_sets['dagger'][25] = item
    original = item.to_dict()
    current_class = state.player.player_class
    state.finish_masterquest_attempt(True)
    assert state.player is None
    assert state.saved_item_sets['dagger'][25].to_dict() == original
    next_class = game.season_class_masterquest_next(state.current_slot_season_id())[current_class]
    state.start_game(next_class)
    assert state.player.level == 1
    assert state.saved_item_sets['dagger'][25].to_dict() == original
    assert state.slots[state.active_slot_index]['saved_item_sets']['dagger']['25'] == original
