"""A quiet recovery decision, with costs, outcomes and the next road in view."""

import json

from nicegui import ui

from .experience_ui import eyebrow, image_plate, text
from .hearth import HearthError, forecast, hearth_for
from .transactions import DesktopTransactionError


def render_hearth(state,game,actions):
    inn = hearth_for(state,game)
    player = state.player
    room = forecast(state,game)
    state.ensure_inn_scene_state(False)

    def rest():
        try:
            inn.rest()
        except (HearthError,DesktopTransactionError) as exc:
            inn.message = str(exc)
        actions['refresh']()

    def resource(label,kind,before,after,maximum):
        gain = after-before
        with ui.element('article').classes('nh-resource '+kind):
            with ui.element('div').classes('nh-resource-heading'):
                ui.label(label)
                ui.label(f'+{gain:,}' if gain else 'RESTORED').classes('nh-resource-gain')
            ui.html(f'<div class="nh-resource-track" role="img" aria-label="{text(label)}: {before:,} now, {after:,} after resting, maximum {maximum:,}">'
                    f'<i class="nh-resource-after" style="width:{100*after/max(1,maximum):.3f}%"></i>'
                    f'<i class="nh-resource-now" style="width:{100*before/max(1,maximum):.3f}%"></i></div>')
            ui.html(f'<div class="nh-resource-values"><span>NOW <b>{before:,}</b></span><span>AFTER ROOM <b>{after:,}</b> / {maximum:,}</span></div>')

    with ui.element('main').classes('nh-workspace'):
        with ui.element('header').classes('nt-scene-header'):
            with ui.element('div'):
                eyebrow('THE WAYFARER\'S INN / RECOVER. SAFEGUARD. RETURN.')
                ui.label('Set down the weight.').classes('nt-display')
            ui.label('A little warmth before the next dark.').classes('nt-header-note')
        with ui.element('div').classes('nh-layout'):
            with ui.element('section').classes('nh-hearth'):
                with ui.element('div').classes('nh-hearth-art'):
                    image_plate(game.get_inn_scene_data_uri(),'The Wayfarer\'s Inn hearth')
                    ui.html('<div class="nh-hearth-halo" aria-hidden="true"></div>')
                with ui.element('div').classes('nh-welcome'):
                    eyebrow('A PLACE THAT ASKS NOTHING OF YOUR BLADE')
                    ui.label(state.current_inn_line or 'The hearth is quiet, but welcoming.').classes('nh-innkeeper')
                receipt = inn.receipt
                with ui.element('div').classes('nh-receipt nt-receipt').props('role=status aria-live=polite') as result:
                    if receipt:
                        result._props['data-town-receipt'] = json.dumps({'key':receipt.key,'kind':'rest','reduced':bool(state.accessibility_reduce_motion)})
                        eyebrow('RESTED / SAVED TO YOUR CHRONICLE')
                        with ui.element('div').classes('nh-receipt-numbers'):
                            ui.label(f'+{receipt.health:,} health').classes('nh-health-text')
                            ui.label(f'+{receipt.mana:,} mana').classes('nh-mana-text')
                            ui.label(f'{receipt.cost:,}g paid' if receipt.cost else 'On the house').classes('nt-gold')
                        ui.label('Your chain was reset. You keep your items, experience and progression.').classes('pd-comparison-note')
                    else:
                        eyebrow('YOUR BREATHING SPACE')
                        ui.label('One room restores 35% of your health and mana capacity, capped at full. No waiting, no full-heal shortcut.').classes('pd-subtle')
                with ui.element('div').classes('nh-safeguards'):
                    with ui.element('article').classes('nh-safeguard'):
                        ui.icon('lock',size='21px')
                        with ui.element('div'):
                            ui.label('Your Inn Vault').classes('nt-section-title')
                            ui.label(f'{len(state.vault_items):,} / {max(state.vault_capacity,len(state.vault_items)):,} slots secured').classes('pd-subtle')
                            ui.label(f'+{game.VAULT_SLOT_BUNDLE_SIZE} slots / {game.VAULT_SLOT_BUNDLE_COST}g. Moving items is free.').classes('pd-comparison-note')
                        ui.button('Open Vault',icon='inventory_2',on_click=actions['vault']).classes('mq-btn-secondary')
                    with ui.element('article').classes('nh-safeguard'):
                        ui.icon('backpack',size='21px')
                        with ui.element('div'):
                            ui.label('Prepare your pack').classes('nt-section-title')
                            ui.label(f'{len(player.inventory):,} items. Inspect, equip and organize.').classes('pd-subtle')
                        ui.button('Open Inventory',on_click=actions['inventory']).classes('mq-btn-secondary')
            with ui.element('aside').classes('nh-room'):
                with ui.element('div').classes('nh-room-scroll'):
                    eyebrow('THE ROOM / ONE DELIBERATE RESET')
                    with ui.element('div').classes('nh-room-title-row'):
                        ui.label('Return renewed.').classes('nt-section-display')
                        ui.html(f'<div class="nh-room-price"><b>{room.cost:,}g</b><small>PER REST</small></div>' if room.cost else '<div class="nh-room-price"><b>Free</b><small>FOR YOUR CLASS</small></div>')
                    resource('HEALTH','health',room.hp_before,room.hp_after,player.max_hp)
                    resource('MANA','mana',room.mana_before,room.mana_after,player.max_mana)
                with ui.element('div').classes('nh-chain '+('has-chain' if room.chain else '')):
                    ui.label(f'CHAIN x{room.chain:,} / RESETS TO x0' if room.chain else 'NO CHAIN TO LOSE').classes('nh-chain-title')
                    ui.label('Resting ends your Monster Chain Combo and its XP bonus. The next victory starts a fresh chain.' if room.chain else 'You can rest without giving up a chain bonus.').classes('pd-subtle')
                with ui.element('footer').classes('nh-room-actions'):
                    if inn.message:
                        ui.label(inn.message).classes('nt-notice error').props('role=alert')
                    if inn.reviewed_chain is not None and room.chain:
                        ui.label(f'Trade your x{room.chain} chain for this recovery?').classes('nh-confirm-copy')
                        with ui.element('div').classes('nh-confirm-actions'):
                            ui.button('Keep My Chain',on_click=lambda:(setattr(inn,'reviewed_chain',None),actions['refresh']())).classes('mq-btn-secondary')
                            ui.button('Rest & Reset Chain',on_click=rest).classes('mq-btn-gold').props('aria-label="Confirm rest and reset chain"')
                    else:
                        blocker = inn.blocker()
                        ui.label(blocker or f'{player.gold-room.cost:,} gold remains after this room.').classes('pd-comparison-note')
                        button = ui.button(f'Take a Room / {room.cost}g' if room.cost else 'Take a Room / Free',icon='local_fire_department',on_click=rest).classes('mq-btn-gold nh-rest-button').props('aria-label="Take a room"')
                        button.set_enabled(not blocker)
                    ready = not room.useful
                    ui.button('Return to Arena',icon='arrow_forward',on_click=lambda:actions['route']('arena')).classes(('mq-btn-gold' if ready else 'mq-btn-secondary')+' nh-road-button')
