import copy
from unittest.mock import patch

import pytest


@pytest.mark.parametrize('slot,subtype,key', [('weapon','Axe','Axe'),('weapon','Dagger','Dagger'),('weapon','Staff','Staff'),('charm','Fire','Fire Charm'),('charm','Ice','Ice Charm'),('charm','Lightning','Lightning Charm')])
def test_every_family_adds_existing_raw_damage_bonus_only(game, slot, subtype, key):
    player = game.create_player('Shadow Mage')
    item = game.Item('Audit piece',slot,45,'Epic',subtype,{'attack_damage_min':100,'attack_damage_max':200},{'enhanced_effect':.5,'intelligence':20})
    player.equipped[slot] = item
    player.proficiency_levels[key] = 10
    before = copy.deepcopy(item.to_dict())
    assert player.get_item_proficiency_bonus(item) == .1
    assert item.get_scaled_base_range('attack_damage',player.get_item_proficiency_bonus(item)) == (141,282)
    assert item.to_dict() == before and item.total_stats()['intelligence'] == 20
    player.proficiency_levels = {name:0 for name in game.PROFICIENCY_TYPES}
    player.proficiency_levels[next(name for name in game.PROFICIENCY_TYPES if name != key)] = 99
    assert player.get_item_proficiency_bonus(item) == 0


@pytest.mark.parametrize('slot,subtype,key', [('weapon','Axe','Axe'),('weapon','Dagger','Dagger'),('weapon','Staff','Staff'),('charm','Fire','Fire Charm'),('charm','Ice','Ice Charm'),('charm','Lightning','Lightning Charm')])
def test_family_bonus_reaches_real_player_damage_without_scaling_other_stats(game,slot,subtype,key):
    player = game.create_player('Shadow Mage')
    player.equipped[slot] = game.Item('Audit piece',slot,45,'Epic',subtype,{'attack_damage_min':100,'attack_damage_max':200},{'enhanced_effect':.5,'intelligence':20})
    player.recalculate_stats()
    family = 'weapon' if slot == 'weapon' else 'spell'
    other = 'spell' if slot == 'weapon' else 'weapon'
    damage = (getattr(player,family+'_attack_min'),getattr(player,family+'_attack_max'))
    unchanged = [getattr(player,name) for name in ['max_hp','max_mana','physical_armor','magic_resistance','cast_mana_cost',other+'_attack_min',other+'_attack_max']]
    player.proficiency_levels[key] = 10
    player.recalculate_stats()
    assert getattr(player,family+'_attack_min') > damage[0]
    assert getattr(player,family+'_attack_max') > damage[1]
    assert [getattr(player,name) for name in ['max_hp','max_mana','physical_armor','magic_resistance','cast_mana_cost',other+'_attack_min',other+'_attack_max']] == unchanged


@pytest.mark.parametrize('caster,mana,hit,key', [(False,100,True,'Axe'),(True,100,True,'Fire Charm'),(True,0,True,'Axe'),(True,100,False,None)])
def test_only_successful_attacking_family_gains_a_point(game, caster, mana, hit, key):
    player = game.create_player('Shadow Mage' if caster else 'Black Guard')
    player.equipped['weapon'] = game.Item('Axe','weapon',1,'Common','Axe',{'attack_damage_min':10,'attack_damage_max':20},{})
    player.equipped['charm'] = game.Item('Flame','charm',1,'Common','Fire',{'attack_damage_min':10,'attack_damage_max':20},{})
    player.base_max_mana = 100
    player.recalculate_stats()
    player.mana = mana
    monster,_ = game.generate_monster(1)
    with patch.object(game,'hit_success',return_value=hit), patch.object(game,'apply_damage',return_value=(10,False,0,0)):
        game.resolve_turn(player,monster)
    assert sum(player.proficiency_progress.values()) == (1 if key else 0)
    if key:
        assert player.proficiency_progress[key] == 1


def test_partial_legacy_progress_does_not_break_a_successful_hit(game):
    player = game.create_player('Black Guard')
    player.proficiency_levels = {'Axe':2}
    player.proficiency_progress = {}
    assert player.grant_proficiency_point('Axe') == (2,2)
    assert player.proficiency_progress['Axe'] == 1


def test_rollover_and_multi_level_awards_preserve_remainder(game):
    player = game.create_player('Black Guard')
    assert player.grant_proficiency_point('Axe',6500) == (0,3)
    assert player.proficiency_progress['Axe'] == 500
    restored = game.Player.from_dict(player.to_dict())
    assert restored.proficiency_levels == player.proficiency_levels
    assert restored.proficiency_progress == player.proficiency_progress


def test_lab_proficiency_level_does_not_wipe_temporary_effects(game):
    player = game.create_player('Black Guard')
    game._labyrinth_apply_effects_to_player(player,{'max_hp_mult':.25,'attack_damage_mult':.25,'evasion':.08})
    stats = (player.max_hp,player.weapon_attack_min,player.weapon_attack_max,player.evasion)
    player.proficiency_progress['Axe'] = 999
    assert player.grant_proficiency_point('Axe') == (0,1)
    assert (player.max_hp,player.weapon_attack_min,player.weapon_attack_max,player.evasion) == stats


def test_next_lab_action_uses_new_proficiency_without_stacking_buffs(game):
    player = game.create_player('Black Guard')
    player.proficiency_progress['Axe'] = 999
    entry = {'player_snapshot':player.to_dict(),'current_hp':player.hp,'current_mana':player.mana}
    effects = {'max_hp_mult':.25,'evasion':.08,'attack_damage_mult':.25}
    actor = game._labyrinth_member_player_from_entry(entry,effects)
    before = actor.weapon_attack_max
    actor.grant_proficiency_point('Axe')
    stored = game._labyrinth_store_entry_from_player(entry,actor)
    next_actor = game._labyrinth_member_player_from_entry(stored,effects)
    assert next_actor.proficiency_levels['Axe'] == 1
    assert next_actor.get_item_proficiency_bonus(next_actor.equipped['weapon']) == .01
    assert next_actor.weapon_attack_max >= before
    assert next_actor.max_hp == actor.max_hp and next_actor.evasion == actor.evasion


def test_proficiency_help_describes_actual_scaling_not_item_ee(game):
    player = game.create_player('Black Guard')
    description = game.build_proficiency_tooltip_html(player)
    assert 'raw item damage' in description
    assert '+1% Enhanced Effect' not in description
