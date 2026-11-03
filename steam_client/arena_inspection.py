"""Compact read-only Arena sheets; the shared Ctrl-inspection portal owns their UI."""

from html import escape


def combat_html(player):
    values = [('Weapon',f'{player.weapon_attack_min:,}-{player.weapon_attack_max:,}'),
              ('Spell',f'{player.spell_attack_min:,}-{player.spell_attack_max:,}'),
              ('Crit',f'{player.crit_chance:.1%}'),('Armor',f'{player.physical_armor:,}'),
              ('Resist',f'{player.magic_resistance:,}'),('Evade',f'{player.evasion:.1%}')]
    return '<section class="pd-insight-sheet"><h3>Combat Stats</h3><dl>'+''.join(
        f'<div><dt>{label}</dt><dd>{value}</dd></div>' for label,value in values)+'</dl></section>'


def proficiency_html(player,game):
    active = set(game.active_proficiency_keys(player))
    rows = []
    for family in game.PROFICIENCY_TYPES:
        level = max(0,int(player.proficiency_levels.get(family,0)))
        current = max(0,int(player.proficiency_progress.get(family,0)))
        threshold = max(1,int(game.proficiency_threshold_for_level(level)))
        rows.append('<div class="pd-insight-prof'+(' active' if family in active else '')+'">'
                    f'<span>{escape(family)}</span><b>Lv {level}</b><small>{current:,} / {threshold:,}</small>'
                    f'<i style="--prof-progress:{min(100,current/threshold*100):.2f}%"></i></div>')
    return '<section class="pd-insight-sheet"><h3>Proficiencies</h3>'+''.join(rows)+'</section>'


def arena_insights_html(player,game,slot):
    paths = {'stats':'M5 18V11M12 18V6M19 18V3M3 21H21',
             'proficiencies':'M4 5H10L12 7L14 5H20V19H14L12 21L10 19H4ZM12 7V21'}
    return '<div class="pd-arena-insights">'+''.join(
        f'<button type="button" class="pd-arena-insight" data-pd-inspect-key="arena-{kind}-{slot}" aria-label="{label}">'
        f'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="{paths[kind]}"/></svg>'
        f'<span class="pd-inspect-content" hidden>{content}</span></button>'
        for kind,label,content in [('stats','Inspect combat stats',combat_html(player)),
                                   ('proficiencies','Inspect proficiencies',proficiency_html(player,game))])+'</div>'
