import copy
import random

import pytest

from steam_client.stat_formulas import (
    CORE_NOTES,
    formula_lines,
    next_point_lines,
    tooltip_html,
)


@pytest.mark.parametrize('stat', list(CORE_NOTES))
def test_forecasts_never_spend_points_mutate_equipment_or_use_rng(game, stat):
    player = game._labyrinth_build_companion_player('Warlock', 45)
    player.unspent_stat_points = 12
    before, rng = copy.deepcopy(player.to_dict()), random.getstate()
    assert next_point_lines(player, stat)
    assert 'Read-only forecast' in tooltip_html(player, stat, game, CORE_NOTES[stat][0])
    assert player.to_dict() == before and random.getstate() == rng


def test_one_vitality_point_forecasts_real_resource_gain(game):
    player = game.create_player('Black Guard')
    expected = f'Max health: {player.max_hp:,} -> {player.max_hp+5:,}'
    assert expected in next_point_lines(player, 'vitality')
    player.base_vitality += 1
    player.recalculate_stats()
    assert expected.endswith(f'-> {player.max_hp:,}')


def test_dexterity_explicitly_explains_initiative_not_attack_speed(game):
    player = game.create_player('Black Guard')
    tooltip = tooltip_html(player, 'dexterity', game, 'Dexterity')
    assert '0.2 x total DEX' in tooltip
    assert 'does not shorten rounds or add attacks' in tooltip
    assert 'Labyrinth uses fixed party order' in tooltip
    assert 'does not directly grant accuracy, evasion or critical chance' in tooltip


@pytest.mark.parametrize('key', ['health','mana','weapon','spell','armor','resistance','critical','evasion','accuracy','initiative'])
def test_every_total_has_nonempty_actual_rule_help(game, key):
    assert formula_lines(game.create_player('Black Guard'), key, game)


def test_formula_text_distinguishes_item_ee_from_proficiency(game):
    tooltip = tooltip_html(game.create_player('Shadow Mage'), 'spell', game, '<Charm>')
    assert '&lt;Charm&gt;' in tooltip
    assert '0.625 x item EE + 0.01 x family proficiency level' in tooltip


def test_forecasts_do_not_walk_the_inventory(game):
    class UntouchedPack(list):
        def __deepcopy__(self, memo):
            raise AssertionError('A stat preview must not copy the pack.')
    player = game.create_player('Black Guard')
    player.inventory = UntouchedPack()
    assert next_point_lines(player, 'vitality')

