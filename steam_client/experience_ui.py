"""Decision-first desktop scenes, separate from the authoritative game rules."""

import html

from nicegui import ui

from .experience import (
    current_result,
    equipment_changes,
    journey_for,
    labyrinth_progress,
    owned_item_index,
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


def render_navigation(state, actions, scene):
    p = state.player
    with ui.element('header').classes('pd-navigation'):
        ui.html(scene_heading(scene, p.player_class, p.level, state.current_slot_title()))
        with ui.element('div').classes('pd-nav-actions'):
            ui.html(f'<span class="pd-currency"><small>GOLD</small>{p.gold:,}</span>')
            if scene != 'town_square':
                home = ui.button('Town', icon='home', on_click=actions['town']).classes('mq-btn-secondary pd-nav-btn').props('aria-label="Return to Town"')
                home.set_enabled(not state.fight_in_progress)
            pack = ui.button('Armory', icon='inventory_2', on_click=actions['inventory']).classes('mq-btn-secondary pd-nav-btn').props('aria-label=Inventory')
            pack.set_enabled(not state.fight_in_progress)
            with ui.button('Chronicle', icon='more_horiz').classes('mq-btn-secondary pd-nav-btn').props('aria-label="Chronicle Menu"') as more:  # noqa: SIM117
                with ui.menu().classes('pd-journal-menu'):
                    for label, callback in [('Character & Stats', lambda: actions['route']('stats')),
                                             ('Chronicle Records', lambda: actions['route']('ladder')),
                                             ('Glossary', lambda: actions['route']('glossary')),
                                             ('Settings', lambda: actions['route']('settings')),
                                             ('Class Selection', actions['classes']),
                                             ('Return to Chronicle Slots', actions['slots'])]:
                        ui.menu_item(label, on_click=callback)
                    if actions.get('tutorial'):
                        ui.menu_item('Tutorial', on_click=actions['tutorial'])
                    if scene == 'town_square':
                        ui.menu_item('Quit to Title', on_click=actions['title'])
            more.set_enabled(not state.fight_in_progress)


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
    monster = state.arena_display_monster()
    active = state.fight_in_progress
    result = current_result(state)
    with ui.element('div').classes('pd-arena-workspace'):
        with ui.element('div').classes('pd-duel-heading'):
            eyebrow('AUTOMATIC COMBAT / YOUR BUILD MAKES THE DIFFERENCE')
            ui.label(f'CHAIN x{state.monster_chain_combo}  /  +{game.get_monster_chain_bonus_fraction(state.monster_chain_combo):.0%} XP').classes('pd-chain')
        with ui.element('section').classes('pd-battle-theatre' + (' is-fighting' if active else '')):
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
                            with ui.element('div').classes(f'pd-found-item pd-find-tier-{game.item_rarity_sort_key(item)}').style(f'--pd-rarity:{game.RARITY_COLORS.get(item.rarity, "#bec9c9")}'):
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
            with ui.element('article').classes('pd-combatant pd-enemy'):
                with ui.element('div').classes('pd-actor-heading'):
                    eyebrow(('LAST CHALLENGER' if not active else 'YOUR OPPONENT') + (f' / LEVEL {monster.level}' if monster else ''))
                    ui.label(game.monster_species_name(monster.monster_type) if monster else 'The unknown').classes('pd-actor-name')
                    ui.label(getattr(monster, 'monster_personal_name', '') or 'Beyond the next gate').classes('pd-actor-subtitle')
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
                for slot, label in [('weapon', 'W'), ('armor', 'A'), ('charm', 'C')]:
                    item = p.equipped.get(slot)
                    button = ui.button(f'{label} / {game.safe_item_name(item) if item else "Empty"}', on_click=actions['inventory']).classes('mq-btn-secondary pd-loadout-item')
                    button.set_enabled(not active)
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
    p = state.player
    with ui.element('div').classes('pd-character-workspace'):
        with ui.element('section').classes('pd-character-build'):
            eyebrow('BUILD YOUR CHAMPION')
            ui.label(p.player_class).classes('pd-character-title')
            ui.label(game.CLASS_DESCRIPTIONS[p.player_class]).classes('pd-subtle')
            ui.label(f'{p.unspent_stat_points} points to allocate').classes('pd-points-available')
            with ui.element('div').classes('pd-stat-allocation-grid'):
                for key, label, note in [('strength', 'Strength', 'Weapon scaling'), ('dexterity', 'Dexterity', 'Weapon scaling / Speed'),
                                         ('intelligence', 'Intelligence', 'Spell scaling / Mana / Resist'), ('vitality', 'Vitality', 'Health / Physical armor')]:
                    with ui.element('div').classes('pd-allocation-card'):
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
                for label, value in [('Health', f'{p.max_hp:,}'), ('Mana', f'{p.max_mana:,}'),
                                     ('Weapon damage', f'{p.weapon_attack_min}-{p.weapon_attack_max}'),
                                     ('Spell damage', f'{p.spell_attack_min}-{p.spell_attack_max}'),
                                     ('Physical armor', str(p.physical_armor)), ('Magic resistance', str(p.magic_resistance)),
                                     ('Critical chance', f'{p.crit_chance:.0%}'), ('Evasion', f'{p.evasion:.0%}')]:
                    ui.html(f'<div><span>{text(label)}</span><b>{text(value)}</b></div>')
            with ui.element('div').classes('pd-proficiency-sheet'):
                ui.html(game.build_proficiency_tooltip_html(p))
            ui.button('Return to Arena', icon='arrow_forward', on_click=lambda: actions['route']('arena')).classes('mq-btn-gold')
