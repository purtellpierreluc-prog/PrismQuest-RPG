"""Read-only explanations and next-point forecasts from the live combat rules."""

import copy
import html

CORE_NOTES = {
    'strength':('Strength','Weapon damage / favors axes'),
    'dexterity':('Dexterity','Weapon damage / initiative, not attack rate'),
    'intelligence':('Intelligence','Charm damage / mana / magic resistance'),
    'vitality':('Vitality','Health / physical armor'),
}


def formula_lines(player, key, game):
    weight = 'Axes: W = 0.95 STR + 0.05 DEX. Daggers: W = 0.05 STR + 0.95 DEX. Staves: W = 0.75 STR + 0.75 DEX.'
    raw = f'Item damage multiplier = 1 + {game.ENHANCED_EFFECT_DAMAGE_POWER:g} x item EE + 0.01 x family proficiency level. EE is a fraction (100% = 1).'
    average = f'Core factor F = {game.CORE_STAT_DAMAGE_POWER:g} x max(0, W / 25). Damage average multiplier = 1 + {game.SPELL_STAT_SCALING_POWER:g} x F.'
    core = {
        'strength':[weight,average,'Strength does not directly grant accuracy, critical chance or attack rate.'],
        'dexterity':[weight,average,'Initiative = max(1, round(base initiative + 0.2 x total DEX)). Higher initiative acts first in Arena and Well; ties are random.','Initiative does not shorten rounds or add attacks. Labyrinth uses fixed party order. DEX does not directly grant accuracy, evasion or critical chance.'],
        'intelligence':['Current max mana = base mana + 5 x total INT + flat mana affixes.','Magic resistance includes round(base resistance + 0.5 x total INT + flat resistance affixes), plus equipped armor.','Charm damage uses W = total INT.',average,'Allocated base INT also adds 5 mana to every future level-up per point; item INT does not.','Charm mana cost depends on its tier, not INT or proficiency.'],
        'vitality':['Current max health = max(1, base health + 5 x total VIT + flat health affixes).','Physical armor includes round(base armor + 0.5 x total VIT + flat armor affixes), plus equipped armor.','Allocated base VIT also adds 5 health to every future level-up per point. Item VIT affects current totals, not permanent level-up growth.'],
        'health':['Max health = max(1, base health + 5 x total VIT + flat health affixes).','Base health already contains your class and historical level-up gains; changing VIT now does not retroactively rewrite earlier level-ups.'],
        'mana':['Max mana = max(0, base mana + 5 x total INT + flat mana affixes).','Base mana includes historical level-up gains. Passive mana recovery is 5 + floor(total INT / 10) per second while alive and out of combat.'],
        'weapon':[raw,weight,average,'Raw item endpoints are rounded first. Spread multiplier = (1 + F) x (1 + min(0.25, 0.07 x item spread / item average)).','Final endpoints are the rounded scaled average +/- half the scaled spread, plus innate attack endpoints. Minimum low is 0; high is at least low + 1 before innate damage.','These are pre-defense ranges, not guaranteed damage.'],
        'spell':[raw,'Charm scaling uses W = total INT.',average,'Spread multiplier = (1 + F) x (1 + min(0.20, 0.05 x item spread / item average)). The engine rounds endpoints and adds innate damage.','Casters use charm damage if they have enough mana; otherwise they use their weapon. Other classes use weapons.'],
        'armor':['Physical armor = max(0, round(base armor + 0.5 x total VIT + flat armor affixes)) + rounded equipped armor average.','Armor item base ranges use multiplier 1 + 1.25 x that armor item\'s EE. Proficiency does not scale armor.','A physical hit subtracts a random roll from 0 to armor, less the attacker\'s flat armor penetration (minimum mitigation 0). Final hit damage is at least 1.'],
        'resistance':['Magic resistance = max(0, round(base resistance + 0.5 x total INT + flat resistance affixes)) + rounded equipped armor resistance average.','Armor EE scales its base resistance. Proficiency does not. A magic hit subtracts a random roll from 0 to resistance; final hit damage is at least 1.'],
        'critical':['Normal critical chance = clamp(base critical chance + item critical affixes, 0%, 85%).','On a critical hit, rolled damage is multiplied by critical damage before defense. STR and DEX do not directly add critical chance. Lab abilities apply separately.'],
        'evasion':['Normal evasion = clamp(base evasion + item evasion affixes, 0%, 35%).','Attacker hit chance = clamp(attacker accuracy - defender evasion, 8%, 100%). DEX does not directly grant evasion. Lab effects and abilities apply separately.'],
        'accuracy':['Accuracy = clamp(base accuracy + item accuracy affixes, 10%, 150%).','Hit chance = clamp(your accuracy - enemy evasion, 8%, 100%). Accuracy above 100% can counter enemy evasion. DEX does not directly increase accuracy.'],
        'initiative':['Initiative = max(1, round(base initiative + 0.2 x total DEX)).','Higher initiative acts first in Arena and Well; ties are 50/50. It is not attack speed, does not shorten rounds and does not add attacks. Labyrinth uses party order.'],
    }
    return core[key]


def next_point_lines(player, key):
    # Recalculation only reads equipped items; never traverse a large pack per preview.
    preview = copy.copy(player)
    preview.equipped = copy.deepcopy(player.equipped)
    preview.proficiency_levels = dict(player.proficiency_levels)
    preview.proficiency_progress = dict(player.proficiency_progress)
    setattr(preview,'base_'+key,getattr(preview,'base_'+key)+1)
    preview.recalculate_stats()
    rows = []
    for attribute,label in [('max_hp','Max health'),('max_mana','Max mana'),('physical_armor','Physical armor'),('magic_resistance','Magic resistance'),('speed','Initiative')]:
        before,after = getattr(player,attribute),getattr(preview,attribute)
        if before != after:
            rows.append(f'{label}: {before:,} -> {after:,}')
    for family,label in [('weapon','Weapon'),('spell','Charm')]:
        before = (getattr(player,family+'_attack_min'),getattr(player,family+'_attack_max'))
        after = (getattr(preview,family+'_attack_min'),getattr(preview,family+'_attack_max'))
        if before != after:
            rows.append(f'{label} range: {before[0]}-{before[1]} -> {after[0]}-{after[1]}')
    return rows or ['No rounded combat total changes on this point. Fractional scaling can cross a rounding threshold on a later point.']


def tooltip_html(player, key, game, title):
    escape = html.escape
    sections = ''.join(f'<p>{escape(line)}</p>' for line in formula_lines(player,key,game))
    if key in CORE_NOTES:
        forecast = ''.join(f'<div>{escape(line)}</div>' for line in next_point_lines(player,key))
        sections += f'<section class="pd-point-preview"><b>IF YOU ALLOCATE ONE POINT NOW</b>{forecast}<small>Read-only forecast, before enemy defenses. No point has been spent.</small></section>'
    return f'<div class="pd-formula-tooltip"><small>YOUR BUILD / THE ACTUAL RULES</small><h3>{escape(title)}</h3>{sections}</div>'
