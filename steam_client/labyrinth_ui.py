"""A bounded expedition: party, light table and a non-overlapping navigation dock."""

import json

from nicegui import ui

from .experience_ui import eyebrow, image_plate, inspect_item_html, text
from .labyrinth import DIRECTIONS, allows, discovery_kind, passages


def inspect_content(key,content):
    return f'<span class="pd-inspect-content" hidden>{content}</span>'


def maze_svg(row):
    size = int(row['grid_size'])
    graph,tiles = passages(row),row['tile_states']
    current = f'{row["current_x"]},{row["current_y"]}'
    visible = {key for key,tile in tiles.items() if tile.get('visited') or tile.get('scouted')}
    for key in list(visible):
        if tiles[key].get('visited'):
            visible.update(graph[key])
    cells,walls,markers = [],[],[]
    for key in graph:
        x,y = map(int,key.split(','))
        tile = tiles[key]
        seen = tile.get('visited')
        scouted = tile.get('scouted') and not seen
        kind = tile.get('kind')
        event = discovery_kind(row,key) if kind=='free' else 'quiet'
        classes = 'visited' if seen else 'scouted' if scouted else 'frontier' if key in visible else 'unknown'
        if key==current:
            classes += ' current'
        cells.append(f'<rect class="pl-cell {classes}" x="{x*100+5}" y="{y*100+5}" width="90" height="90" rx="7" data-room="{key}"/>')
        if key in visible:
            for direction,(dx,dy) in DIRECTIONS.items():
                if f'{x+dx},{y+dy}' in graph[key]:
                    continue
                ax,ay,bx,by = {'up':(0,0,100,0),'down':(0,100,100,100),'left':(0,0,0,100),'right':(100,0,100,100)}[direction]
                walls.append(f'<path d="M{x*100+ax},{y*100+ay} L{x*100+bx},{y*100+by}"/>')
        if key==current:
            markers.append(f'<g transform="translate({x*100+50},{y*100+50})" class="pl-you"><circle r="28"/><path d="M0,-17 12,0 0,17 -12,0Z"/></g>')
        elif seen or scouted:
            symbol = 'G' if kind=='start' else ('x' if seen else '!') if kind in {'encounter','boss'} else '+' if event in {'hearth','sanctuary'} else '~' if event=='tide' else '*' if event=='mirror' else '.'
            markers.append(f'<text x="{x*100+50}" y="{y*100+53}" class="pl-map-mark {"discovery" if event!="quiet" else ""}">{symbol}</text>')
        elif key in visible:
            markers.append(f'<circle cx="{x*100+50}" cy="{y*100+50}" r="5" class="pl-frontier-dot"/>')
    return (f'<svg class="pl-maze" viewBox="-8 -8 {size*100+16} {size*100+16}" role="img" aria-label="Labyrinth maze. Party at column {row["current_x"]+1}, row {row["current_y"]+1}. Bright borders are walls; openings are passages.">'
            '<defs><radialGradient id="pl-map-light"><stop stop-color="#243c3e"/><stop offset="1" stop-color="#0a171e"/></radialGradient></defs>'
            f'<rect x="-8" y="-8" width="{size*100+16}" height="{size*100+16}" rx="10" fill="url(#pl-map-light)"/>'
            +''.join(cells)+'<g class="pl-walls">'+''.join(walls)+'</g>'+''.join(markers)+'</svg>')


def _party(state,game,row,action):
    pending = row.get('pending_encounter',{})
    party = game._labyrinth_party_state_map(pending)
    active = row.get('status') in {'encounter','boss'}
    low = state.labyrinth_low_load_mode
    for index,raw in enumerate(state.labyrinth_member_rows):
        member = game._labyrinth_project_member_row(raw,party)
        identity,hero_class = member['user_id'],member['player_class']
        companion = member.get('is_companion',False)
        owned = identity==game._labyrinth_member_identity(state) or (state.labyrinth_is_local and companion)
        ability = game._labyrinth_entry_ability_state(member)
        meta = game._labyrinth_class_ability_meta(hero_class)
        ready = game._labyrinth_ability_ready(member,row) and meta.get('type')!='passive'
        clickable = owned and ready and row.get('status')=='exploring' and not member.get('is_downed')
        healing = hero_class=='Warlock' and ability.get('toggle_on')
        with ui.element('article').classes('pl-member'+(' mq-lab-member-downed' if member.get('is_downed') else '')+(' is-healing' if healing else '')).props(f'id=mq-lab-member-{index}'):
            with ui.element('button').classes('pl-portrait mq-hero-art-frame'+(' pl-ready' if clickable else '')).props(f'type=button data-pd-inspect-key="lab-ability-{identity}" aria-label="{text(member.get("character_name") or hero_class)} ability" aria-disabled={str(not clickable).lower()}') as portrait:
                image_plate(game._hero_data_uri(hero_class),hero_class,'pl-hero-art')
                ui.html(inspect_content(identity,game.labyrinth_ability_hover_panel_html(member,row))).style('display:none')
                if clickable:
                    portrait.on('click',lambda who=identity:action(lambda:state.labyrinth_activate_ability(who)))
            with ui.element('div').classes('pl-member-main'):
                with ui.element('div').classes('pl-member-heading'):
                    with ui.element('div').classes('pl-member-name'):
                        ui.label(str(member.get('character_name') or hero_class) if not companion or member.get('roster_companion_id') else hero_class).classes('pl-name')
                        ui.label(f'{hero_class} / {member.get("level",45)}' if not companion or member.get('roster_companion_id') else f'Level {member.get("level",45)}').classes('pl-class')
                    tank = bool(member.get('tank'))
                    toggle = ui.button('T ON' if tank else 'T OFF',color=None,on_click=lambda who=identity,value=tank:action(lambda:state.labyrinth_set_tank_role(who,not value))).classes('mq-btn-secondary mq-lab-tank-btn').props('aria-pressed='+str(tank).lower())
                    toggle.set_enabled(owned and not active)
                with ui.element('div').classes('pl-resource-stack'):
                    for name,label,current,maximum,duration in [('hp','Health',member['current_hp'],member['max_hp'],900),('mana','Mana',member['current_mana'],member['max_mana'],1200)]:
                        with ui.element('div').classes('mq-meter-shell pl-meter-wrap').props(f'tabindex=0 data-pd-inspect-key="lab-{name}-{identity}" aria-label="{label}"'):
                            ui.html(game.animated_meter_html(f'lab-party-{name}-{index}',label,current,max(1,maximum),name,0 if low else duration))
                            ui.html(inspect_content(name,game.labyrinth_meter_hover_panel_html(label,current,maximum))).style('display:none')
                            if name=='hp':
                                ui.html(game._labyrinth_damage_popup_html(state.labyrinth_visual_damage_popups,identity,low_load=low))
                with ui.element('div').classes('pl-member-foot'):
                    ui.label('Healing mode' if healing else 'Downed' if member.get('is_downed') else 'Ability ready' if clickable else 'Passive' if meta.get('type')=='passive' else game._labyrinth_ability_status_text(member,row)).classes('pl-ability-note')
                    if companion:
                        equipped = member.get('combat_snapshot',{}).get('equipped',{})
                        with ui.element('div').classes('pl-gear'):
                            for slot,short in [('weapon','W'),('armor','A'),('charm','C')]:
                                item = game.coerce_item(equipped.get(slot))
                                ui.html(inspect_item_html(item,game,key=f'lab-gear-{identity}-{slot}',caption=short)).classes('pl-gear-token')


def _monsters(state,game,row):
    pending = row['pending_encounter']
    monsters = game._labyrinth_monster_snapshots_from_pending(pending)
    boss = bool(pending.get('boss'))
    eyebrow('THE FLOOR GUARDIAN' if boss else 'ACTIVE ENCOUNTER')
    ui.label(f'Round {pending.get("round",1)} / Group volley').classes('pl-round').props('id=mq-lab-round-note')
    with ui.element('div').classes('pl-monsters'+(' is-boss' if boss else '')):
        for index,monster in enumerate(monsters):
            with ui.element('article').classes('pl-monster').style(game.monster_theme_style(monster['monster_type'])):
                image_plate(game._arena_monster_data_uri(monster['monster_type']),monster['monster_type'],'pl-monster-art')
                with ui.element('div').classes('pl-monster-info'):
                    ui.label(game.monster_species_name(monster['monster_type'])+f' / {monster["level"]}').classes('pl-monster-name').props(f'id=mq-lab-monster-heading-{index}')
                    with ui.element('div').classes('mq-meter-shell'):
                        suffix = '' if len(monsters)==1 else f'-{index}'
                        ui.html(game.animated_meter_html('labyrinth-monster-hp'+suffix,'Health',monster['hp'],monster['max_hp'],'hp',0 if state.labyrinth_low_load_mode else 900))
                        ui.html(game._labyrinth_damage_popup_html(state.labyrinth_visual_damage_popups,f'monster-{index}',low_load=state.labyrinth_low_load_mode))
                    if boss:
                        with ui.element('dl').classes('pl-boss-stats'):
                            for label,value in [('Attack',f'{monster["attack_min"]}-{monster["attack_max"]}'),('Armor',monster['physical_armor']),('Resistance',monster['magic_resistance']),('School',monster['damage_school'].title())]:
                                ui.html(f'<div><dt>{label}</dt><dd>{text(value)}</dd></div>')


def _rewards(state,game,row,action):
    eyebrow('THE GUARDIAN FALLS')
    ui.label('Choose the next light.').classes('pl-title')
    ui.label('One boon. One burden. Both stay with this expedition.').classes('pl-subtle')
    ui.label(f'{game._labyrinth_reward_seconds_remaining(row)}s to choose').classes('pl-vote-clock')
    gain = row.get('pending_encounter',{}).get('reward_gold_gain',0)
    if gain:
        ui.label(f'+{gain:,} gold / +1 level').classes('pl-payoff')
    with ui.element('div').classes('pl-prism-choices'):
        for choice in row.get('reward_options',[]):
            index = choice['choice_index']
            selected = state.labyrinth_current_vote_choice()==index
            with ui.element('article').classes('pl-prism-choice'+(' selected' if selected else '')):
                eyebrow(f'PRISM {index+1:02}')
                ui.label(choice.get('title','Unstable Prism')).classes('pl-choice-title')
                ui.label(choice.get('boon','')).classes('pl-boon')
                ui.label(choice.get('bane','')).classes('pl-bane')
                button = ui.button('Chosen' if selected else 'Choose This Prism',on_click=lambda i=index:action(lambda:state.vote_labyrinth_reward(i))).classes('mq-btn-gold')
                button.set_enabled(not selected)
    if state.labyrinth_is_leader():
        ui.button('Seal the Vote and Advance',icon='north_east',on_click=lambda:action(state.finalize_labyrinth_reward_vote)).classes('mq-btn-gold pl-seal')


def _company(state,game,row,action):
    eyebrow('YOUR COMPANY / GEAR AND PROFICIENCY CARRY FORWARD')
    ui.label('Bring a little light with you.').classes('pl-title')
    busy = row.get('status') in {'encounter','boss'}
    available = max(0,game.LABYRINTH_MAX_PARTY_SIZE-len(state.labyrinth_member_rows))
    ui.label(f'{available} party slots open. Hired allies: 100g per expedition. Owned allies: free to add.').classes('pl-subtle')
    with ui.element('div').classes('pl-company-scroll'):
        entries = game.normalize_labyrinth_roster_companions(state.labyrinth_roster_companions)
        owned = {entry['player_class'] for entry in entries}
        active = {member.get('roster_companion_id') for member in state.labyrinth_member_rows}
        with ui.element('section').classes('pl-recruit'):
            classes = {name:name for name in game.ALL_CLASS_ORDER}
            draft = state.labyrinth_companion_class_draft
            select = ui.select(classes,label='Companion class',value=draft if draft in classes else state.player.player_class).props('outlined dense')
            select.on_value_change(lambda e:setattr(state,'labyrinth_companion_class_draft',e.value))
            def hire():
                action(lambda:state.labyrinth_hire_companion(select.value))
            def purchase():
                action(lambda:state.labyrinth_buy_roster_companion(select.value))
            hire_btn = ui.button('Hire / 100g',on_click=hire).classes('mq-btn-secondary')
            hire_btn.set_enabled(not busy and available>0 and state.player.gold>=game.LABYRINTH_COMPANION_COST)
            buy_btn = ui.button('Own Permanently / 1,000g',on_click=purchase).classes('mq-btn-gold')
            buy_btn.set_enabled(not busy and select.value not in owned and state.player.gold>=game.LABYRINTH_ROSTER_COMPANION_COST)
            select.on_value_change(lambda e:buy_btn.set_enabled(not busy and e.value not in owned and state.player.gold>=game.LABYRINTH_ROSTER_COMPANION_COST))
        if not entries:
            ui.label('Your permanent roster starts here. Each class can be purchased once.').classes('pl-empty')
        for entry in entries:
            identity = entry['id']
            preview = game._labyrinth_build_roster_companion_player(entry,game._labyrinth_roster_target_level(state))
            with ui.element('article').classes('pl-roster-card'):
                with ui.element('div').classes('pl-roster-head'):
                    image_plate(game._hero_data_uri(entry['player_class']),entry['player_class'],'pl-roster-art')
                    with ui.element('div').classes('pl-roster-identity'):
                        name = ui.input('Companion name',value=entry.get('custom_name') or entry['player_class']).props('outlined dense maxlength=28')
                        ui.label(f'{entry["player_class"]} / Level {preview.level}').classes('pl-subtle')
                    ui.button('Save Name',on_click=lambda who=identity,field=name:action(lambda:state.labyrinth_rename_roster_companion(who,field.value))).classes('mq-btn-secondary').set_enabled(not busy)
                    ui.button('In Party' if identity in active else 'Add to Expedition',on_click=lambda who=identity:action(lambda:state.labyrinth_add_roster_companion_to_expedition(who))).classes('mq-btn-gold').set_enabled(not busy and available>0 and identity not in active)
                with ui.element('div').classes('pl-roster-equipment'):
                    for slot in ('weapon','armor','charm'):
                        item = preview.equipped.get(slot)
                        options = {str(i):candidate.summary() for i,candidate in enumerate(state.player.inventory) if candidate.slot==slot and game.can_player_equip_item(preview,candidate)[0]}
                        with ui.element('div').classes('pl-roster-slot'):
                            ui.html(inspect_item_html(item,game,key=f'roster-{identity}-{slot}',caption=slot.title()))
                            field = ui.select(options,label='From your pack',value=None).props('outlined dense clearable')
                            with ui.element('div').classes('pl-roster-slot-actions'):
                                equip = ui.button('Equip',on_click=lambda who=identity,s=slot,f=field:action(lambda:state.labyrinth_set_roster_companion_item(who,s,f.value or ''))).classes('mq-btn-secondary')
                                equip.set_enabled(False)
                                field.on_value_change(lambda e,b=equip:b.set_enabled(not busy and e.value is not None))
                                ui.button('Return',on_click=lambda who=identity,s=slot:action(lambda:state.labyrinth_clear_roster_companion_item(who,s))).classes('mq-btn-secondary').set_enabled(not busy and item is not None)


def render_labyrinth(state,game,actions):
    row = state.labyrinth_session_row
    def action(operation):
        operation()
        actions['refresh']()
    def company():
        state.labyrinth_panel_view = 'expedition' if state.labyrinth_panel_view=='roster' else 'roster'
        state._desktop_lab_journal = False
        actions['refresh']()
    def leave():
        if state.leave_labyrinth_session():
            state.enter_town('You leave the Labyrinth of Light behind.')
        actions['refresh']()
    management = state.labyrinth_panel_view=='roster'
    journal = bool(getattr(state,'_desktop_lab_journal',False))
    moving = bool(row and row.get('status')=='exploring' and not management and not journal)
    ui.run_javascript(f'window.mqSetLabyrinthKeysEnabled && window.mqSetLabyrinthKeysEnabled({json.dumps(moving)});')
    with ui.element('main').classes('pl-workspace'):
        if not row:
            with ui.element('section').classes('pl-entry'):
                ui.html('<svg class="pl-entry-prism" viewBox="0 0 200 240" aria-hidden="true"><path d="M100 10 178 105 100 230 22 105Z M100 10 100 230 M22 105 178 105 M22 105 100 155 178 105"/></svg>')
                eyebrow('LABYRINTH OF LIGHT / LEVEL 45+')
                ui.label('Some paths must be earned.').classes('pl-entry-title')
                ui.label('Find the passages. Explore every room. Defeat the guardian and choose the cost of going deeper.').classes('pl-entry-copy')
                button = ui.button('Create Solo Expedition',icon='north_east',on_click=lambda:action(state.create_labyrinth_solo_session)).classes('mq-btn-gold')
                blocker = state.labyrinth_route_blocker()
                button.set_enabled(not blocker)
                if blocker:
                    ui.label(blocker).classes('pl-subtle')
            return
        status = row.get('status')
        active = status in {'encounter','boss'}
        tiles = row['tile_states']
        cleared = sum(bool(tile.get('resolved')) for tile in tiles.values())
        with ui.element('header').classes('pl-header'):
            with ui.element('div'):
                eyebrow(f'LABYRINTH OF LIGHT / FLOOR {row["floor"]:02}')
                ui.label('Company & supplies' if management else 'The light remembers.' if journal else 'The floor guardian' if status=='boss' else 'Prism covenant' if status=='reward' else 'Follow the openings.').classes('pl-title')
            with ui.element('div').classes('pl-run-totals'):
                ui.label(f'{cleared:02} / {len(tiles)} rooms').classes('pl-progress')
                ui.label(f'{game._labyrinth_pending_run_gold(row):,}g earned').classes('pl-gold')
                with ui.element('button').classes('pl-prisms').props('type=button tabindex=0 data-pd-inspect-key=lab-prisms aria-label="Accumulated prism rewards"'):
                    ui.label(f'{len(row.get("modifier_stack",[]))} prisms')
                    ui.html(inspect_content('prisms',game.labyrinth_active_prism_hover_panel_html(row.get('modifier_stack',[]),game._labyrinth_pending_run_gold(row)))).style('display:none')
        with ui.element('div').classes('pl-layout'):
            with ui.element('aside').classes('pl-company'):
                with ui.element('div').classes('pl-party-heading'):
                    eyebrow(f'YOUR PARTY / {len(state.labyrinth_member_rows)} OF 5')
                    ui.label('Ctrl + hover to inspect').classes('pl-key-hint')
                with ui.element('div').classes('pl-party-scroll'):
                    _party(state,game,row,action)
            with ui.element('section').classes('pl-stage'+(' pl-management' if management or journal else '')).props('aria-label="Labyrinth play area"'):
                if management:
                    _company(state,game,row,action)
                elif journal:
                    eyebrow('EXPEDITION JOURNAL')
                    ui.label('The light remembers.').classes('pl-title')
                    with ui.element('div').classes('pl-journal'):
                        discoveries = row.get('pending_encounter',{}).get('discovery_log',[])
                        for record in discoveries:
                            with ui.element('article'):
                                eyebrow(f'FLOOR {record["floor"]} / ROOM {record["tile"]}')
                                ui.label(record['title']).classes('pl-choice-title')
                                ui.label(record['detail']).classes('pl-subtle')
                        for event in row.get('recent_events',[])[:12]:
                            ui.label(event).classes('pl-subtle')
                elif active:
                    _monsters(state,game,row)
                elif status=='reward':
                    _rewards(state,game,row,action)
                elif status=='defeated':
                    eyebrow('THE LIGHT HAS NOT LEFT YOU')
                    ui.label('Regather at the gate.').classes('pl-title')
                    ui.label('Reform your party and retry this floor.').classes('pl-subtle')
                    ui.button('Reform at the Prism Gate',on_click=lambda:action(state.labyrinth_reset_after_defeat)).classes('mq-btn-gold')
                else:
                    with ui.element('div').classes('pl-map-topline'):
                        ui.label('THE LIGHT TABLE').classes('pd-eyebrow')
                        ui.label(f'Column {row["current_x"]+1} / Row {row["current_y"]+1}').classes('pl-coordinate')
                    with ui.element('div').classes('pl-maze-wrap'):
                        ui.html(maze_svg(row))
                    with ui.element('div').classes('pl-map-legend'):
                        ui.label('G Gate / x Cleared / ! Threat / + Font / ~ Mana / * Mirror').classes('pl-subtle')
                        ui.label('Bright edges are walls. Dots lead into the unknown.').classes('pl-key-hint')
                    discovery = row.get('pending_encounter',{}).get('discovery',{})
                    with ui.element('div').classes('pl-discovery') as receipt:
                        if discovery and discovery.get('floor')==row['floor']:
                            if discovery.get('kind')!='quiet':
                                receipt._props['data-town-receipt'] = json.dumps({'key':discovery['id'],'reduced':bool(state.accessibility_reduce_motion or state.labyrinth_low_load_mode)})
                            ui.label(discovery['title']).classes('pl-discovery-title')
                            ui.label(discovery['detail']).classes('pl-subtle')
                        else:
                            ui.label('The gate is your anchor.').classes('pl-discovery-title')
                            ui.label('Explore all rooms to wake the guardian. Cleared paths stay safe.').classes('pl-subtle')
            with ui.element('aside').classes('pl-dock'):
                eyebrow('EXPEDITION')
                if status=='lobby':
                    ui.button('Start Floor',icon='north_east',on_click=lambda:action(state.labyrinth_start_floor)).classes('mq-btn-gold pl-dock-start')
                elif status=='exploring':
                    ui.label('Navigate').classes('pl-dock-title')
                else:
                    ui.label('Fighting' if active else 'Choose a prism' if status=='reward' else 'Regroup').classes('pl-dock-title')
                with ui.element('div').classes('pl-direction-pad'):
                    for direction,icon in [('up','north'),('left','west'),('down','south'),('right','east')]:
                        button = ui.button(icon=icon,on_click=lambda d=direction:action(lambda:state.labyrinth_move_party(d))).classes('mq-btn-secondary pl-direction pl-'+direction).props(f'id=mq-lab-move-{direction} aria-label="Move {direction}"')
                        button.set_enabled(moving and allows(row,direction))
                ui.label('Arrow keys / WASD').classes('pl-key-hint')
                with ui.element('div').classes('pl-dock-links'):
                    ui.button('Back to Maze' if management else 'Roster',icon='groups',on_click=company).classes('mq-btn-secondary').set_enabled(not active)
                    ui.button('Open Inventory',icon='inventory_2',on_click=actions['inventory']).classes('mq-btn-secondary').set_enabled(not active)
                    def toggle_journal():
                        state._desktop_lab_journal = not bool(getattr(state,'_desktop_lab_journal',False))
                        state.labyrinth_panel_view = 'expedition'
                        actions['refresh']()
                    ui.button('Close Journal' if journal else 'Journal',icon='menu_book',on_click=toggle_journal).classes('mq-btn-secondary').set_enabled(not active)
                ui.label(str(state.labyrinth_status)).classes('pl-status').props('role=status aria-live=polite')
                with ui.element('footer').classes('pl-dock-footer'):
                    ui.button('Refresh',icon='refresh',on_click=lambda:action(lambda:state.refresh_labyrinth_session_state(force=True))).classes('mq-btn-secondary').props('aria-label="Refresh Expedition"')
                    ui.button('Leave',icon='logout',on_click=leave).classes('mq-btn-secondary').set_enabled(not active)
