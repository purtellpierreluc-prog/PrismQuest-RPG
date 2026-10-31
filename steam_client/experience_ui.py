"""Decision-first desktop scenes, separate from the authoritative game rules."""

import html
import json

from nicegui import ui

from .experience import (
    ITEM_TYPE_COLORS,
    arena_opponent,
    chronicle_preview,
    current_result,
    encounter_signal,
    equipment_changes,
    item_visual_style,
    journey_for,
    labyrinth_progress,
    monster_defense_cue,
    monster_signature,
    owned_item_index,
    saved_archive_marks,
)
from .visuals import scene_heading


def text(value):
    return html.escape(str(value), quote=True)


def eyebrow(label):
    ui.label(label).classes('pd-eyebrow')


def image_plate(uri, alt, classes=''):
    with ui.element('div').classes('pd-art-plate ' + classes):
        if uri:
            ui.html(f'<img src="{text(uri)}" alt="{text(alt)}" decoding="async" draggable="false">')
        else:
            ui.label(alt).classes('pd-art-fallback')


def render_chronicles(state, game, refresh):
    with ui.element('main').classes('pd-chronicle-workspace'):
        with ui.element('header').classes('pd-chronicle-heading'):
            with ui.element('div'):
                eyebrow('PRISMQUEST / LOCAL CHRONICLES')
                ui.label('Choose your legend.').classes('pd-chronicle-title')
                ui.label('Three independent roads. Each keeps its own hero and everything they have earned.').classes('pd-subtle')
            ui.button('Back to Title', icon='arrow_back', on_click=lambda: (state.return_to_title(), refresh())).classes('mq-btn-secondary')
        with ui.element('div').classes('pd-chronicle-deck'):
            for index, (mode, detail, theme) in enumerate([
                ('Core', 'The classic ascent', 'gold'), ('SSF', 'A self-found chronicle', 'silver'),
                ('HC', 'A life with consequences', 'blood')]):
                preview = chronicle_preview(state.slots[index])
                with ui.element('article').classes(f'pd-save-card pd-save-{theme}'):
                    with ui.element('div').classes('pd-save-header'):
                        ui.label(f'0{index+1} / {mode.upper()}').classes('pd-eyebrow')
                        ui.label('CONTINUE' if preview.occupied else 'NEW CHRONICLE').classes('pd-save-state')
                    ui.label(detail).classes('pd-save-mode')
                    image_plate(game._hero_data_uri(preview.player_class) if preview.player_class in game.CLASS_DESCRIPTIONS else '',
                                preview.player_class or 'Your story begins here', 'pd-save-art')
                    with ui.element('div').classes('pd-save-description'):
                        ui.label(preview.name).classes('pd-save-name')
                        ui.label(f'{preview.player_class} / Level {preview.level}' if preview.occupied else 'Choose a class and begin the climb.').classes('pd-subtle')
                        if preview.occupied:
                            ui.html(f'<div class="pd-save-facts"><span><b>{preview.gold:,}</b>GOLD</span><span><b>{preview.wins:,}</b>VICTORIES</span><span><b>{preview.items:,}</b>PACK ITEMS</span></div>')
                        else:
                            ui.label('No existing character will be replaced.').classes('pd-comparison-note')
                    ui.label('EXPEDITION READY TO RESUME' if preview.expedition else 'OFFLINE / SAVED ON THIS MACHINE').classes('pd-save-location')
                    ui.button('Continue Chronicle' if preview.occupied else 'Begin Chronicle', icon='arrow_forward',
                              on_click=lambda idx=index: (state.open_slot(idx), refresh())).classes('mq-btn-gold pd-save-open').props(f'aria-label="Open {mode}"')
        ui.label('Items, vaults, unlocks, companions and expedition progress stay with their chronicle.').classes('pd-chronicle-footer')


def inspect_item_html(item, game, *, key, caption):
    name = game.safe_item_name(item) if item else 'Empty slot'
    content = game.build_item_hover_tooltip_html(item) if item else '<div class="pd-subtle">Nothing equipped in this slot.</div>'
    return (f'<button type="button" class="pd-inspect-trigger" data-pd-inspect-key="{text(key)}" '
            f'aria-label="Inspect equipped {text(caption)}" style="{text(item_visual_style(item, game))}">'
            f'<span class="pd-inspect-caption">{text(caption)}</span><span class="pd-inspect-name">{text(name)}</span>'
            f'<span class="pd-inspect-tier">{("T" + str(game.item_required_level(item))) if item else "--"}</span>'
            f'<span class="pd-inspect-content" hidden>{content}</span></button>')


def last_find_html(state, game):
    item = getattr(state, 'last_monster_drop_item', None)
    name = game.equipped_item_display_name(item) if item else 'No find yet'
    icon = game.item_icon_uri(item) if item else ''
    art = (f'<img src="{text(icon)}" alt="" decoding="async" draggable="false">' if icon else
           '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 8 8-5 8 5v10l-8 4-8-4Zm0 0 8 5 8-5M12 13v9"/></svg>')
    source = {'arena': 'Arena', 'well': 'Well of Evil', 'labyrinth': 'Labyrinth'}.get(getattr(state, 'last_monster_drop_source', ''), 'Monster')
    content = game.build_item_hover_tooltip_html(item) if item else '<div class="pd-subtle">Your latest monster drop will stay here during subsequent fights.</div>'
    if item:
        content += f'<div class="pd-last-find-note">Last drop / {text(source)}. Read-only record, even if the item has since moved.</div>'
    return (f'<button type="button" class="pd-last-find" data-pd-inspect-key="arena-last-find" '
            f'aria-label="Inspect last dropped item" style="{text(item_visual_style(item, game))}">'
            f'<span class="pd-last-find-icon">{art}</span><span class="pd-last-find-copy"><small>LAST DROP</small>'
            f'<b>{text(name)}</b></span><span class="pd-last-find-tier">{("T" + str(game.item_required_level(item))) if item else "--"}</span>'
            f'<span class="pd-inspect-content" hidden>{content}</span></button>')


def render_item_sheet(title, item, game, empty_text):
    with ui.card().classes('mq-card mq-inv-detail-panel pd-item-sheet pd-item-surface w-full').style(item_visual_style(item, game)):
        eyebrow(title)
        if item is None:
            ui.label(empty_text).classes('pd-item-empty')
            return
        color = game.RARITY_COLORS.get(item.rarity, '#bdc9c9')
        with ui.element('div').classes('pd-item-sheet-heading').style(f'--pd-rarity:{color}'):
            image_plate(game.item_icon_uri(item), item.subtype, 'pd-item-icon')
            with ui.element('div'):
                ui.label(f'{item.rarity.upper()} / TIER {game.item_required_level(item)}').classes('pd-item-rarity')
                ui.label(game.safe_item_name(item)).classes('pd-item-sheet-name')
                ui.label(item.subtype).classes('pd-subtle')
        ui.html(game.inventory_base_detail_html(item))
        eyebrow('AFFIXES')
        ui.html(game.inventory_affix_detail_html(item))
        ui.label(f'Merchant value / {game.safe_item_sell_value(item)} gold').classes('pd-item-value')


def render_manifest_contents(item, game, *, selected=False, saved=False, archive=False):
    if archive:
        with ui.element('div').classes('pd-archive-item-copy'):
            ui.label(item.rarity.upper()).classes('pd-item-rarity')
            ui.label(game.equipped_item_display_name(item)).classes('mq-inv-entry-title')
            ui.label(game.safe_item_base_stat_text(item)).classes('pd-pack-base')
            ui.html('<span class="mq-manifest-flag selected">Selected</span>' if selected else '<span class="pd-archive-inspect-hint">Hover for full stats</span>')
        return
    color = game.RARITY_COLORS.get(item.rarity, '#bdc9c9')
    with ui.element('div').classes('pd-pack-entry').style(f'--pd-rarity:{color}'):
        image_plate(game.item_icon_uri(item), item.subtype, 'pd-pack-icon')
        with ui.element('div').classes('pd-pack-entry-copy'):
            ui.label(f'{item.rarity.upper()} / TIER {game.item_required_level(item)}' + (' / PROTECTED' if saved else '')).classes('pd-item-rarity')
            ui.label(game.safe_item_name(item)).classes('mq-inv-entry-title')
            ui.label(game.safe_item_base_stat_text(item)).classes('pd-pack-base')
            count = max(0, len(item.affix_stats) - 2)
            ui.label(game.safe_item_affix_preview_text(item) + (f' / +{count} more' if count else '')).classes('pd-pack-affixes')
        with ui.element('div').classes('pd-pack-entry-end'):
            ui.label(f'{game.safe_item_sell_value(item)}g').classes('pd-item-value')
            ui.html('<span class="mq-manifest-flag selected">Selected</span>' if selected else '<span class="pd-selection-mark" aria-hidden="true">+</span>')


def render_saved_archive(state, view, game, render_entry, toggle):
    tiers = list(reversed(game.ITEM_BUCKETS)) if state.tier_filter == 'All tiers' else [int(state.tier_filter.replace('Tier', '').strip())]
    categories = [key for key in game.SAVED_ITEM_SET_ORDER if state.type_filter == 'All types' or game.SAVED_ITEM_SET_LABELS[key] == state.type_filter]
    if not any(state.saved_item_sets.get(category) for category in game.SAVED_ITEM_SET_ORDER):
        with ui.element('div').classes('pd-collection-empty pd-archive-empty-message'):
            ui.label('Your next run starts with what you save.').classes('pd-subtle')
            ui.label('Save a piece from Inventory to fill its type and tier mark.').classes('pd-comparison-note')
    with ui.element('div').classes('pd-saved-archive'):
        for category in categories:
            label = game.SAVED_ITEM_SET_LABELS[category]
            marks = saved_archive_marks(category, tiers, view['entries'], state.saved_item_sets)
            shown = sum(mark.item is not None for mark in marks)
            stored = sum(mark.occupied for mark in marks)
            collapsed = bool(state.saved_set_collapsed.get(category, False))
            with ui.element('section').classes('pd-saved-family').style(f'--pd-type:{ITEM_TYPE_COLORS[category]}'):
                with ui.element('div').classes('pd-saved-family-heading'):
                    ui.button(label, icon='chevron_right' if collapsed else 'expand_more',
                              on_click=lambda family=category: toggle(family)).classes('mq-btn-secondary pd-saved-family-toggle').props(f'aria-label="Toggle {label} saved marks" aria-expanded={str(not collapsed).lower()}')
                    ui.label(f'{stored} SAVED / {len(marks)} MARKS' + (f' / {shown} SHOWN' if shown != stored else '')).classes('pd-comparison-note')
                if collapsed:
                    continue
                with ui.element('div').classes('pd-saved-tier-grid').props(f'role=listbox aria-label="{label} saved tiers"'):
                    for mark in marks:
                        with ui.element('div').classes('pd-saved-mark').props(f'data-saved-category={category} data-saved-tier={mark.tier}'):
                            ui.label(f'TIER {mark.tier:02}').classes('pd-saved-tier-label')
                            if mark.item is not None:
                                render_entry('saved', (category, mark.tier), mark.item, archive=True)
                            else:
                                with ui.element('div').classes('pd-saved-empty-mark' + (' filtered' if mark.occupied else '')):
                                    ui.label('Filtered item' if mark.occupied else 'Empty mark')
                                    ui.label('Change filters to inspect' if mark.occupied else f'Keep a Tier {mark.tier} {label} here').classes('pd-comparison-note')


def render_item_legend(game):
    types = ''.join(f'<span style="--pd-type:{ITEM_TYPE_COLORS[key]}">{text(label)}</span>' for key, label in game.SAVED_ITEM_SET_LABELS.items())
    rarities = ''.join(f'<span style="--pd-rarity:{text(color)}">{text(rarity)}</span>' for rarity, color in game.RARITY_COLORS.items() if rarity != 'Unspawnable')
    ui.html('<details class="pd-item-key"><summary>Border = type / wash = rarity</summary><div class="pd-item-key-popover">'
            '<b>ITEM TYPE / BORDER</b><div class="pd-item-key-types">' + types + '</div>'
            '<b>RARITY / BACKGROUND</b><div class="pd-item-key-rarities">' + rarities + '</div>'
            '<p>Names and icons repeat the color cues. Gold selection markers are separate.</p></div></details>')


def render_combat_stats(player):
    with ui.element('dl').classes('pd-combat-stats').props('aria-label="Champion combat stats"'):
        for label, value in [('Weapon', f'{player.weapon_attack_min:,}-{player.weapon_attack_max:,}'),
                             ('Spell', f'{player.spell_attack_min:,}-{player.spell_attack_max:,}'),
                             ('Crit', f'{player.crit_chance:.1%}'), ('Armor', f'{player.physical_armor:,}'),
                             ('Resist', f'{player.magic_resistance:,}'), ('Evade', f'{player.evasion:.1%}')]:
            ui.html(f'<div><dt>{text(label)}</dt><dd>{text(value)}</dd></div>')


def render_navigation(state, actions, scene):
    p = state.player
    rite = getattr(state, '_desktop_ascension', None)
    well = getattr(state, '_desktop_well', None)
    locked = bool(state.fight_in_progress or (rite is not None and (
        rite.busy or rite.pending_verdict is not None or
        (state.game_tab == 'masterquest' and rite.started and not rite.receipt))) or
        (well is not None and (well.pending or well.interrupted)))
    with ui.element('header').classes('pd-navigation'):
        ui.html(scene_heading(scene, p.player_class, p.level, state.current_slot_title()))
        with ui.element('div').classes('pd-nav-actions'):
            ui.html(f'<span class="pd-currency"><small>GOLD</small>{p.gold:,}</span>')
            if scene != 'town_square':
                home = ui.button('Town', icon='home', on_click=actions['town']).classes('mq-btn-secondary pd-nav-btn').props('aria-label="Return to Town"')
                home.set_enabled(not locked)
            pack = ui.button('Armory', icon='inventory_2', on_click=actions['inventory']).classes('mq-btn-secondary pd-nav-btn').props('aria-label=Inventory')
            pack.set_enabled(not locked)
            with ui.button('Chronicle', icon='more_horiz').classes('mq-btn-secondary pd-nav-btn').props('aria-label="Chronicle Menu"') as more:  # noqa: SIM117
                with ui.menu().classes('pd-journal-menu'):
                    for label, callback in [('Character & Stats', lambda: actions['route']('stats')),
                                             ('Chronicle Records', lambda: actions['route']('ladder')),
                                             ('Concourse / Network', lambda: actions['route']('network')),
                                             ('Glossary', lambda: actions['route']('glossary')),
                                             ('Settings', lambda: actions['route']('settings')),
                                             ('Class Selection', actions['classes']),
                                             ('Return to Chronicle Slots', actions['slots'])]:
                        ui.menu_item(label, on_click=callback)
                    if actions.get('tutorial'):
                        ui.menu_item('Tutorial', on_click=actions['tutorial'])
                    if scene == 'town_square':
                        ui.menu_item('Quit to Title', on_click=actions['title'])
            more.set_enabled(not locked)


def _journey(state):
    blocker = state.masterquest_entry_blocker()
    return journey_for(state.player, quest_available=not bool(blocker), quest_blocker=blocker,
                       lab_active=bool(getattr(state, 'labyrinth_session_row', {})))


def render_journey(state, game, *, compact=False):
    p = state.player
    goal = _journey(state)
    with ui.element('div').classes('pd-journey compact' if compact else 'pd-journey'):
        with ui.element('div').classes('pd-journey-copy'):
            eyebrow(goal.milestone)
            ui.label(goal.title).classes('pd-journey-title')
        ui.html(game.animated_meter_html('player-xp', f'LEVEL {p.level}', p.xp, max(1, p.xp_to_next), 'exp', 4200, cycle=p.level, rollover=True))
        with ui.element('div').classes('pd-milestone-track'):
            for level, label in [(1, 'AWAKEN'), (45, 'LABYRINTH'), (60, 'ASCEND')]:
                ui.html(f'<span class="{"reached" if p.level >= level else ""}"><b>{level:02}</b>{label}</span>')


def render_town(state, game, actions):
    p = state.player
    goal = _journey(state)
    with ui.element('div').classes('pd-town-workspace'):
        render_navigation(state, actions, 'town_square')
        with ui.element('div').classes('pd-town-main'):
            with ui.element('section').classes('pd-purpose-card'):
                eyebrow('YOUR NEXT CHAPTER')
                ui.label(goal.title).classes('pd-purpose-title')
                ui.label(goal.detail).classes('pd-purpose-detail')
                ui.button(goal.action, icon='arrow_forward', on_click=lambda: actions['route'](goal.destination)).classes('mq-btn-gold pd-purpose-action')
                with ui.element('div').classes('pd-town-hero'):
                    image_plate(game._hero_data_uri(p.player_class), p.player_class)
                    with ui.element('div'):
                        ui.label(p.name).classes('pd-town-hero-name')
                        ui.label(f'{p.player_class} / Level {p.level}').classes('pd-subtle')
                        ui.html(game.animated_meter_html('town-hp', 'HEALTH', p.hp, p.max_hp, 'hp', 800))
                        ui.html(game.animated_meter_html('town-mana', 'MANA', p.mana, max(1, p.max_mana), 'mana', 800))
                render_journey(state, game)
            with ui.element('section').classes('pd-crossroads'):
                with ui.element('div').classes('pd-world-label'):
                    eyebrow('BETWEEN DARKNESS AND THE PRISM')
                    ui.label('Choose your road.').classes('pd-world-title')
                image_plate(game.get_town_scene_data_uri(), 'The town crossroads', 'pd-town-map')
                with ui.element('div').classes('pd-destination-deck'):
                    destinations = [
                        ('01', 'Arena', 'Experience & equipment', 'arena', ''),
                        ('02', 'Labyrinth of Light', 'Lead your party beyond the cap', 'labyrinth', state.labyrinth_route_blocker()),
                        ('03', 'Prismatic Quest', 'Risk the ritual. Unlock a new class.', 'masterquest', state.masterquest_entry_blocker()),
                    ]
                    for number, title, detail, destination, blocker in destinations:
                        with ui.element('div').classes('pd-destination' + (' locked' if blocker else '')):
                            ui.label(number).classes('pd-destination-number')
                            ui.label(detail).classes('pd-destination-copy')
                            button = ui.button(title, icon='lock' if blocker else 'north_east', on_click=lambda route=destination: actions['route'](route)).classes('mq-btn-secondary pd-destination-btn')
                            if blocker:
                                button.disable()
                            ui.label(str(blocker) if blocker else 'READY TO ENTER').classes('pd-destination-lock')
        with ui.element('section').classes('pd-services'):
            eyebrow('PREPARE FOR THE NEXT ROAD')
            with ui.element('div').classes('pd-service-deck'):
                for title, detail, icon, route in [
                    ('Inn', 'Recover / Vault', 'local_fire_department', 'inn'),
                    ('Inventory', 'Inspect / Equip', 'inventory_2', 'inventory'),
                    ('Marketplace', 'Find new equipment', 'storefront', 'marketplace'),
                    ('Transmutation', 'Combine your finds', 'auto_fix_high', 'transmute'),
                    ('Well of Evil', 'Offer / Risk / Discover', 'water_drop', 'well')]:
                    with ui.element('div').classes('pd-service'):
                        ui.button(title, icon=icon, on_click=lambda dest=route: actions['route'](dest)).classes('mq-btn-secondary pd-service-btn').props('aria-label=' + ('Inventory' if route == 'inventory' else '"' + title + '"'))
                        ui.label(detail).classes('pd-service-description')
        with ui.element('footer').classes('pd-town-footer'):
            ui.label(f'{p.wins} victories / {p.losses} defeats / {len(p.inventory)} items in pack').classes('pd-subtle')
            ui.button('Concourse', icon='public', on_click=lambda: actions['route']('network')).classes('mq-btn-secondary pd-text-btn')
            with ui.button('Town Crier', icon='campaign').classes('mq-btn-secondary pd-text-btn'):  # noqa: SIM117
                with ui.menu():
                    ui.label(state.town_crier_status_text()).classes('pd-crier-copy')
            ui.button('Settings', icon='settings', on_click=lambda: actions['route']('settings')).classes('mq-btn-secondary pd-text-btn')
            ui.button('Quit to Title', on_click=actions['title']).classes('mq-btn-secondary pd-text-btn')


def _battle_round(state):
    for event in reversed(state.log[-60:]):
        if event.tag == 'round':
            return str(event.text).strip('- ').upper()
    return 'THE GATES OPEN'


def _reveal_once(element_id, key, disabled):
    if disabled:
        return
    ui.run_javascript(f'''(() => {{
      const el = document.getElementById({element_id!r});
      const key = {key!r};
      const seen = window.pdResultSeen = window.pdResultSeen || [];
      if (!el || seen.includes(key)) return;
      seen.push(key); if (seen.length > 32) seen.shift();
      el.classList.add('pd-result-arrive');
    }})();''')


def render_arena(state, game, actions):
    p = state.player
    monster = arena_opponent(state)
    active = state.fight_in_progress
    result = current_result(state)
    with ui.element('div').classes('pd-arena-workspace'):
        with ui.element('div').classes('pd-duel-heading'):
            eyebrow('AUTOMATIC COMBAT / YOUR BUILD MAKES THE DIFFERENCE')
            with ui.element('div').classes('pd-encounter-tools'):
                ui.label(f'CHAIN x{state.monster_chain_combo}  /  +{game.get_monster_chain_bonus_fraction(state.monster_chain_combo):.0%} XP').classes('pd-chain')
                ui.html(last_find_html(state, game))
        signal = encounter_signal(state, monster)
        with ui.element('section').classes('pd-battle-theatre' + (' is-fighting' if active else '')).props(f'data-pd-phase={signal["phase"]}') as theatre:
            theatre._props['data-pd-encounter'] = json.dumps(signal, separators=(',', ':'))
            ui.element('div').classes('pd-encounter-trace').props('aria-hidden=true')
            with ui.element('article').classes('pd-combatant pd-hero'):
                with ui.element('div').classes('pd-actor-heading'):
                    eyebrow(f'YOUR CHAMPION / LEVEL {p.level}')
                    ui.label(p.name).classes('pd-actor-name')
                    ui.label(p.player_class).classes('pd-actor-subtitle')
                image_plate(game._hero_data_uri(p.player_class), p.player_class, 'pd-hero-art')
                with ui.element('div').classes('pd-actor-resources'):
                    with ui.element('div').classes('mq-meter-shell'):
                        ui.html(game.animated_meter_html('player-hp', 'HEALTH', p.hp, p.max_hp, 'hp', 1800))
                        popup = state.get_damage_popup_html('player')
                        if popup:
                            ui.html(popup)
                    ui.html(game.animated_meter_html('player-mana', 'MANA', p.mana, max(1, p.max_mana), 'mana', 2600))
                    render_combat_stats(p)
            with ui.element('section').classes('pd-battle-focus'):
                if active:
                    eyebrow('LIVE ENCOUNTER')
                    ui.label(_battle_round(state) if not state.monster_page_turn_active else 'CHALLENGER APPROACHING').classes('pd-round')
                    ui.html('<div class="pd-versus-mark" aria-hidden="true"><span>VS</span></div>')
                    live = next((event for event in reversed(state.log[-10:]) if event.tag != 'round'), None)
                    ui.label(live.text if live else 'Your build is put to the test.').classes('pd-live-event')
                    ui.label('You and your opponent act automatically.').classes('pd-focus-note')
                elif result:
                    outcome = result.outcome
                    eyebrow('ENCOUNTER RESOLVED')
                    ui.label('Victory' if outcome == 'victory' else 'Regroup' if outcome == 'defeat' else 'Escaped').classes('pd-result-title ' + outcome)
                    ui.label('A little closer to the light.' if outcome == 'victory' else 'A setback is not the end of your chronicle.').classes('pd-focus-note')
                    with ui.element('div').classes('pd-result-receipt').props('id=pd-battle-receipt'):
                        with ui.element('div').classes('pd-reward-totals'):
                            if result.xp == 0 and p.level >= 60 and outcome == 'victory':
                                ui.html('<span><b>60+</b>ARENA XP CAP</span>')
                            else:
                                ui.html(f'<span><b>{result.xp:+,}</b>XP progress</span>')
                            if result.gold:
                                ui.html(f'<span><b>{result.gold:+,}</b>Gold</span>')
                            if result.levels:
                                ui.html(f'<span class="pd-level-earned"><b>+{result.levels}</b>LEVEL</span>')
                        if result.item is not None:
                            item = result.item
                            with ui.element('div').classes(f'pd-found-item pd-item-surface pd-find-tier-{game.item_rarity_sort_key(item)}').style(item_visual_style(item, game)):
                                eyebrow('NEW DISCOVERY / ' + item.rarity.upper())
                                ui.label(game.safe_item_name(item)).classes('pd-found-name')
                                ui.label(f'Tier {game.item_required_level(item)} / {game.safe_item_base_stat_text(item)}').classes('pd-found-base')
                                ui.label(game.safe_item_affix_preview_text(item)).classes('pd-found-affix')
                                if owned_item_index(p, item) is not None:
                                    ui.button('Inspect This Find', icon='compare_arrows', on_click=lambda: actions['review'](item)).classes('mq-btn-secondary pd-review-find')
                                else:
                                    ui.label('Already moved or equipped.').classes('pd-subtle')
                        else:
                            note = 'No equipment this time. Your experience still counts.' if result.xp > 0 else 'No equipment this time. Prepare for the prism, or continue into the Labyrinth.'
                            ui.label(note if outcome == 'victory' else 'Recover, adjust your build, and return stronger.').classes('pd-no-drop')
                    _reveal_once('pd-battle-receipt', f'{state.active_slot_index}:{result.serial}', bool(state.disable_last_drop_animation))
                    if outcome == 'defeat' or p.hp < p.max_hp * .3:
                        ui.button('Recover at the Inn', icon='local_fire_department', on_click=lambda: actions['route']('inn')).classes('mq-btn-secondary pd-recovery')
                elif state.last_fight_outcome == 'fled':
                    eyebrow('ENCOUNTER ENDED')
                    ui.label('Escaped').classes('pd-result-title')
                    ui.label('Your chain was reset. Recover or adjust your build before calling the next challenger.').classes('pd-focus-note')
                else:
                    eyebrow('THE NEXT CHALLENGER AWAITS')
                    ui.label('Test your\nresolve.').classes('pd-idle-title')
                    ui.html('<div class="pd-versus-mark" aria-hidden="true"><span>VS</span></div>')
                    ui.label('Choose your difficulty, call a challenger, and let your build speak.').classes('pd-focus-note')
            cue = monster_defense_cue(monster, game.monster_late_game_scale)
            signature, texture = monster_signature(monster.monster_type if monster else '')
            with ui.element('article').classes('pd-combatant pd-enemy').style(game.monster_theme_style(monster.monster_type if monster else '')).props(f'data-defense={cue.kind} data-species-texture={texture}'):
                if monster:
                    ui.element('div').classes('pd-species-texture').props('aria-hidden=true')
                with ui.element('div').classes('pd-actor-heading'):
                    eyebrow(('LAST CHALLENGER' if not active else 'YOUR OPPONENT') + (f' / LEVEL {monster.level}' if monster else ''))
                    ui.label(game.monster_species_name(monster.monster_type) if monster else 'The unknown').classes('pd-actor-name')
                    ui.label(getattr(monster, 'monster_personal_name', '') or 'Beyond the next gate').classes('pd-actor-subtitle')
                    if monster:
                        ui.label(signature).classes('pd-monster-signature').props('title="Species atmosphere only. Armor and resistance are identified separately."')
                    if cue.label:
                        ui.label(cue.label).classes('pd-defense-cue').props(f'title="{text(cue.description)}"')
                image_plate(state.arena_monster_uri(monster) if monster else '', monster.monster_type if monster else 'Call a challenger', 'pd-enemy-art')
                with ui.element('div').classes('pd-actor-resources'):
                    if monster:
                        with ui.element('div').classes('mq-meter-shell'):
                            key = f'monster-hp-{monster.monster_type}-{monster.level}' if state.current_monster is not None else 'monster-preview-hp'
                            ui.html(game.animated_meter_html(key, 'HEALTH', monster.hp, monster.max_hp, 'hp', 1800))
                            popup = state.get_damage_popup_html('monster')
                            if popup and active:
                                ui.html(popup)
                        ui.label(f'{monster.damage_school.upper()} / ATK {monster.attack_min}-{monster.attack_max} / ARM {monster.physical_armor} / RES {monster.magic_resistance}').classes('pd-enemy-readout')
                    else:
                        ui.label('Opponent details appear here when combat begins.').classes('pd-enemy-readout')
        with ui.element('div').classes('pd-command-deck'):
            with ui.element('div').classes('pd-command-left'):
                with ui.button(f'Target / LV {state.arena_target_level()}', icon='tune').classes('mq-btn-secondary pd-tactics-btn').props('aria-label="Encounter Settings"') as tactics:  # noqa: SIM117
                    with ui.menu().classes('pd-tactics-menu'):
                        eyebrow('SET THE CHALLENGE')
                        ui.label('Lower-level enemies reduce XP. Fight your level for the full reward.').classes('pd-subtle')
                        def same_changed(event):
                            state.arena_same_level = bool(event.value)
                            actions['refresh']()
                        def target_changed(event):
                            if event.value is not None:
                                state.arena_selected_level = int(event.value)
                                actions['refresh']()
                        limit = max(1, min(60, p.level))
                        ui.checkbox('Always fight your level', value=state.arena_same_level, on_change=same_changed)
                        select = ui.select({n: f'Level {n}' for n in range(1, limit + 1)}, label='Target level', value=state.arena_target_level(), on_change=target_changed).props('outlined dense')
                        select.set_enabled(not state.arena_same_level)
                        ui.number('Auto level offset', value=int(state.arena_level_offset), min=0, max=limit-1, step=1,
                                  on_change=lambda e: (setattr(state, 'arena_level_offset', max(0, min(limit-1, int(e.value or 0)))), actions['refresh']())).props('outlined dense')
                tactics.set_enabled(not active)
                ui.label('Automatic rounds. Deliberate preparation.').classes('pd-command-hint')
            with ui.element('div').classes('pd-command-primary'):
                fight = ui.button('In Combat' if active else 'Next Challenger' if result else 'Call Challenger', icon='flash_on', on_click=actions['fight']).classes('mq-btn-gold pd-fight-btn').props('aria-label=Fight')
                fight.set_enabled(not active)
                if active:
                    flee = ui.button('Flee', on_click=lambda: (state.request_arena_flee(), actions['refresh']())).classes('mq-btn-secondary pd-text-btn')
                    flee.set_enabled(state.current_monster is not None and not state.arena_flee_requested and not state.monster_page_turn_active)
                else:
                    ui.label('Your next decision is yours. No automatic restart.').classes('pd-command-hint')
            with ui.element('div').classes('pd-command-right'):
                build = ui.button(f'Build / {p.unspent_stat_points} points' if p.unspent_stat_points else 'Character & Stats', icon='person', on_click=lambda: actions['route']('stats')).classes('mq-btn-secondary pd-build-btn')
                build.set_enabled(not active)
                if p.unspent_stat_points:
                    build.classes('pd-attention')
                with ui.button('Battle Record', icon='format_list_bulleted').classes('mq-btn-secondary pd-text-btn').props('aria-label="Battle Record"') as record:  # noqa: SIM117
                    with ui.menu().classes('pd-record-menu'):
                        eyebrow('RECENT COMBAT')
                        for event in state.log[-35:]:
                            ui.label(event.text).classes('pd-record-line ' + str(event.tag))
                record.set_enabled(not active)
                record.props('title="Full record is available between encounters"')
        with ui.element('div').classes('pd-arena-understory'):
            with ui.element('div').classes('pd-loadout-strip'):
                eyebrow('YOUR LOADOUT')
                for slot in ('weapon', 'armor', 'charm'):
                    item = p.equipped.get(slot)
                    ui.html(inspect_item_html(item, game, key=f'arena-equipped-{slot}', caption=slot.title())).classes('pd-loadout-item')
            render_journey(state, game, compact=True)


def render_equipment_decision(player, item, game):
    with ui.element('section').classes('pd-equipment-decision'):
        eyebrow('IF YOU EQUIP THIS')
        if item is None:
            ui.label('Select a find to see how it changes your build.').classes('pd-subtle')
            return
        reason, changes = equipment_changes(player, item, game.can_player_equip_item)
        if reason:
            ui.label(reason).classes('pd-equip-blocker')
            ui.label('You can still save, sell, or keep this item.').classes('pd-subtle')
            return
        ui.label('Your stats and proficiency included. Damage averages are before enemy defenses.').classes('pd-comparison-note')
        if not changes:
            ui.label('No change to the tracked combat stats. Compare the affixes below for other effects.').classes('pd-subtle')
        for change in changes:
            with ui.element('div').classes('pd-stat-delta'):
                ui.label(change.label)
                ui.label(f'{change.formatted(change.before)} > {change.formatted(change.after)}').classes('pd-delta-values')
                ui.label(('+' if change.delta > 0 else '-') + change.formatted(abs(change.delta))).classes('positive' if change.delta > 0 else 'negative')
        ui.label('Trade-offs are shown, not reduced to a misleading gear score.').classes('pd-comparison-note')


def render_expedition_brief(row):
    cleared, total = labyrinth_progress(row)
    status = str(row.get('status', '')).lower()
    if status in {'encounter', 'boss'}:
        title = 'Defeat the guardian' if status == 'boss' else 'Your party is in combat'
        note = 'Each living party member acts, then the monsters answer.'
    elif status == 'reward':
        title, note = 'Choose what changes your next floor', 'One benefit. One sacrifice. Effects last for this expedition.'
    else:
        title, note = 'Bring light to every square', f'{total-cleared} squares remain. Clear them all to reveal the floor guardian.'
    with ui.element('div').classes('pd-expedition-brief'):
        with ui.element('div'):
            eyebrow(f'FLOOR {max(1, int(row.get("floor", 1) or 1)):02} / {status.upper() or "PREPARE"}')
            ui.label(title).classes('pd-expedition-title')
            ui.label(note).classes('pd-expedition-note')
        ui.html(f'<div class="pd-explore-progress"><b>{cleared}<small>/{total}</small></b><span>ILLUMINATED</span><div style="--pd-progress:{cleared/total*100:.2f}%"></div></div>')


def render_character(state, game, actions):
    from .stat_formulas import CORE_NOTES, tooltip_html
    p = state.player
    with ui.element('div').classes('pd-character-workspace'):
        with ui.element('section').classes('pd-character-build'):
            eyebrow('BUILD YOUR CHAMPION')
            ui.label(p.player_class).classes('pd-character-title')
            ui.label(game.CLASS_DESCRIPTIONS[p.player_class]).classes('pd-subtle')
            ui.label(f'{p.unspent_stat_points} points to allocate').classes('pd-points-available')
            with ui.element('div').classes('pd-stat-allocation-grid'):
                for key, (label,note) in CORE_NOTES.items():
                    with ui.element('div').classes('pd-allocation-card').props(f'tabindex=0 data-pd-inspect-key="core-{state.active_slot_index}-{key}" aria-label="{label} formula and next point preview"'):
                        ui.html('<span class="pd-inspect-content" hidden>'+tooltip_html(p,key,game,label)+'</span>').style('display:none')
                        ui.label(label).classes('pd-allocation-name')
                        ui.label(str(getattr(p, key))).classes('pd-allocation-value')
                        ui.label(note).classes('pd-comparison-note')
                        with ui.element('div').classes('pd-allocation-actions'):
                            for amount, caption in [(1, '+1'), (p.unspent_stat_points, 'All')]:
                                button = ui.button(caption, on_click=lambda stat=key, n=amount: (state.allocate_multiple(stat, n), actions['refresh']())).classes('mq-btn-secondary').props(f'aria-label="{caption} {label}"')
                                button.set_enabled(not state.fight_in_progress and p.unspent_stat_points > 0)
            ui.label('Allocation affects future level-up resource growth. Choose deliberately.').classes('pd-comparison-note')
        with ui.element('section').classes('pd-character-readout'):
            eyebrow('YOUR BUILD IN PRACTICE')
            with ui.element('div').classes('pd-character-totals'):
                for key,label,value in [('health','Health',f'{p.max_hp:,}'),('mana','Mana',f'{p.max_mana:,}'),
                                        ('weapon','Weapon damage',f'{p.weapon_attack_min}-{p.weapon_attack_max}'),('spell','Spell damage',f'{p.spell_attack_min}-{p.spell_attack_max}'),
                                        ('armor','Physical armor',str(p.physical_armor)),('resistance','Magic resistance',str(p.magic_resistance)),
                                        ('critical','Critical chance',f'{p.crit_chance:.0%}'),('evasion','Evasion',f'{p.evasion:.0%}'),
                                        ('accuracy','Accuracy',f'{p.accuracy:.0%}'),('initiative','Initiative',str(p.speed))]:
                    ui.html(f'<div class="pd-total-formula" tabindex="0" data-pd-inspect-key="total-{state.active_slot_index}-{key}" aria-label="{text(label)} formula"><span>{text(label)} <small>?</small></span><b>{text(value)}</b>'
                            '<span class="pd-inspect-content" hidden>'+tooltip_html(p,key,game,label)+'</span></div>')
            with ui.element('div').classes('pd-proficiency-sheet'):
                ui.html(game.build_proficiency_tooltip_html(p))
            ui.button('Return to Arena', icon='arrow_forward', on_click=lambda: actions['route']('arena')).classes('mq-btn-gold')
