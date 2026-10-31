"""The Well: choose a keepsake, understand the bargain, face its answer."""

import json

from nicegui import ui

from .experience import item_visual_style, owned_item_index
from .experience_ui import eyebrow, image_plate, text
from .well import WellError, well_for


def render_well(state,game,actions):
    well = well_for(state,game)
    player = state.player

    def refresh():
        actions['refresh']()

    def choose(item):
        try:
            well.select(item)
        except WellError as exc:
            well.message = str(exc)
        shelf.refresh()
        ritual.refresh()

    def filter_changed(key,value):
        setattr(well,key,value)
        well.selected = well.armed = None
        shelf.refresh()
        ritual.refresh()

    def review():
        try:
            well.arm()
        except WellError as exc:
            well.message = str(exc)
        ritual.refresh()

    async def commit():
        try:
            await well.commit(refresh)
        except WellError as exc:
            well.message = str(exc)
        refresh()

    async def recover():
        try:
            if well.pending:
                await well.retry_settlement(refresh)
            else:
                await well.resume(refresh)
        except WellError as exc:
            well.message = str(exc)
        refresh()

    @ui.refreshable
    def shelf():
        rows = [item for item in player.inventory if item.rarity == 'Common'
                and (well.tier == 'All tiers' or game.item_required_level(item) == well.tier)
                and (well.kind == 'All types' or game.saved_item_type_label(item) == well.kind)
                and well.search.casefold() in (game.safe_item_name(item)+' '+game.saved_item_type_label(item)).casefold()]
        ui.label(f'{len(rows)} COMMON OFFERINGS / PACK ONLY').classes('pd-comparison-note')
        with ui.element('div').classes('pw-shelf').props('aria-label="Common offerings"') as library:
            library._props['data-pw-shelf'] = well.session
            library._props['data-pw-filter'] = json.dumps([well.search,well.tier,well.kind])
            if not rows:
                with ui.element('div').classes('pw-library-empty'):
                    ui.label('Nothing for the deep.').classes('pw-subtitle')
                    ui.label('Bring a Common item, or clear your filters. Equipped, saved and vaulted gear cannot be offered here.').classes('pd-subtle')
            for item in rows:
                selected = well.selected is item
                with ui.button(on_click=lambda candidate=item:choose(candidate)).classes('pw-offering'+(' selected' if selected else '')).style(item_visual_style(item,game)).props(f'aria-label="Offer {text(game.safe_item_name(item))}, Tier {game.item_required_level(item)}" aria-pressed={str(selected).lower()} data-pw-item="{id(item)}" data-pd-inspect-key="well-offer-{id(item)}"') as row:
                    row.set_enabled(player.level>=game.item_required_level(item) and not well.pending and not well.interrupted)
                    ui.html(f'<img src="{text(game.item_icon_uri(item))}" alt="" draggable="false"><span><small>{"SELECTED / " if selected else ""}TIER {game.item_required_level(item)}</small><b>{text(game.saved_item_type_label(item))}</b><em>{text(game.safe_item_short_stat_text(item))}</em></span>'
                            f'<span class="pd-inspect-content" hidden>{game.build_item_hover_tooltip_html(item)}</span>')

    @ui.refreshable
    def ritual():
        item = well.selected if well.owns(well.selected) else None
        with ui.element('section').classes('pw-altar'):
            with ui.element('div').classes('pw-altar-reading'):
                with ui.element('div').classes('pw-art'):
                    image_plate(game.get_well_scene_data_uri(),'The Well of Evil and its handmaiden')
                    ui.html('<div class="pw-water-ring" aria-hidden="true"></div>')
                eyebrow('THE BARGAIN')
                ui.label('A keepsake for the dark.').classes('pw-altar-title')
                ui.label('Win the encounter. Then the well decides what comes back.').classes('pd-subtle')
                with ui.element('div').classes('pw-vitals'):
                    ui.html(game.animated_meter_html('player-hp','HEALTH',player.hp,player.max_hp,'hp',700))
                    ui.html(game.animated_meter_html('player-mana','MANA',player.mana,max(1,player.max_mana),'mana',700))
                with ui.element('div').classes('pw-terms'):
                    ui.html('<span><b>10g</b><small>PAID ON ENTRY</small></span><span><b>1 Common</b><small>CONSUMED OFFERING</small></span><span><b>50%</b><small>ITEM RETURN ON VICTORY</small></span>')
                if item:
                    with ui.element('div').classes('pw-chosen').style(item_visual_style(item,game)):
                        image_plate(game.item_icon_uri(item),'Selected offering','pw-chosen-icon')
                        with ui.element('div'):
                            ui.label(game.safe_item_name(item)).classes('pw-chosen-name')
                            ui.label(f'Tier {game.item_required_level(item)} / {game.saved_item_type_label(item)}').classes('pd-subtle')
                else:
                    ui.label('Choose a Common item from your pack. No offering is preselected.').classes('pw-select-prompt')
                ui.label('A returned item keeps the offering\'s tier and type. Rarity uses your normal Magic Find; affixes use the Well\'s favorable roll. A stronger item is not guaranteed.').classes('pd-comparison-note')
                if player.hp < player.max_hp*.35:
                    ui.label('Your health is low. The Wellspawn is stronger than a normal challenger; consider recovering at the Inn.').classes('pw-warning')
            with ui.element('footer').classes('pw-commit-zone'):
                if well.pending or well.interrupted:
                    ui.label(well.message).classes('pw-warning').props('role=alert')
                    ui.button('Retry Saving Outcome' if well.pending else 'Continue Encounter',icon='refresh',on_click=recover).classes('mq-btn-gold')
                elif well.armed and not well.blocker():
                    ui.label(f'Consume {game.safe_item_name(item)} and 10 gold? Neither is returned if you lose or withdraw.').classes('pw-confirm-copy')
                    with ui.element('div').classes('pw-confirm-actions'):
                        ui.button('Not Yet',on_click=lambda:(setattr(well,'armed',None),ritual.refresh())).classes('mq-btn-secondary')
                        ui.button('Cast Offering / 10g',icon='water_drop',on_click=commit).classes('mq-btn-gold')
                else:
                    ui.label(well.message or well.blocker() or f'{player.gold-10:,} gold remains after the offering. The Common item is consumed.').classes('pw-commit-copy')
                    button = ui.button('Review the Bargain',icon='water_drop',on_click=review).classes('mq-btn-gold pw-primary')
                    button.set_enabled(not well.blocker())

    def answer():
        receipt = well.receipt
        item = receipt.item if receipt else None
        with ui.element('section').classes('pw-answer').style(item_visual_style(item,game) if item else '') as result:
            if receipt:
                result._props['data-pw-result'] = json.dumps({'key':receipt.key,'outcome':receipt.outcome,'rarity':getattr(item,'rarity','Common'),'reduced':bool(state.accessibility_reduce_motion or state.disable_last_drop_animation)})
            eyebrow('THE DEEP\'S ANSWER / LAST BARGAIN')
            if receipt is None:
                with ui.element('div').classes('pw-empty-result'):
                    ui.icon('water_drop',size='46px')
                    ui.label('The surface is still.').classes('pw-result-title')
                    ui.label('Your answer appears here after combat. Even a victory can return nothing.').classes('pd-subtle')
                return
            with ui.element('div').classes('pw-answer-body'):
                if item:
                    ui.html(game.safe_rarity_badge_html(item))
                    ui.label(game.safe_item_name(item)).classes('pw-result-title')
                    ui.label(f'Tier {receipt.tier} / {receipt.item_type}').classes('pw-result-meta')
                    ui.label('Returned to your pack. Already saved; no claim step.').classes('pw-saved-note')
                    with ui.element('div').classes('pw-affixes'):
                        eyebrow('WHAT THE DEEP WROTE INTO IT')
                        ui.html(game.inventory_affix_detail_html(item))
                else:
                    ui.icon('water_drop' if receipt.outcome == 'miss' else 'shield',size='38px').classes('pw-empty-glyph')
                    ui.label('The well kept its prize.' if receipt.outcome == 'miss' else 'You returned without a prize.').classes('pw-result-title')
                    ui.label('You won the encounter, but the 50% return roll yielded no item.' if receipt.outcome == 'miss' else 'You withdrew from the encounter.' if receipt.outcome == 'fled' else 'The Wellspawn prevailed. Recover before another bargain.').classes('pd-subtle')
                    ui.label(f'10 gold and the Common Tier {receipt.tier} {receipt.item_type} were consumed.').classes('pw-result-meta')
                    ui.label('No item was returned. Nothing is waiting to be claimed.').classes('pd-comparison-note')
            if item:
                inspect = ui.button('Inspect Returned Item',icon='inventory_2',on_click=lambda:actions['review'](receipt.owned_item)).classes('mq-btn-secondary pw-inspect')
                owned = state.player is not None and owned_item_index(state.player,receipt.owned_item) is not None
                inspect.set_enabled(owned)
                if not owned:
                    ui.label('Read-only record. This item is no longer in your pack.').classes('pd-comparison-note')
            ui.html('<div class="pw-answer-veil" aria-hidden="true"><span class="pw-ripple"></span><span>The surface stirs.</span><button type="button" data-pw-skip>Reveal now</button></div>')

    with ui.element('main').classes('pw-workspace'):
        with ui.element('header').classes('pw-header'):
            with ui.element('div'):
                eyebrow('WELL OF EVIL / A BARGAIN WITH THE DEEP')
                ui.label('Some things are worth the risk.').classes('pw-title')
            ui.label('Same tier. Same type. A different fate.').classes('pw-header-note')
        with ui.element('div').classes('pw-columns'):
            with ui.element('section').classes('pw-library'):
                eyebrow('01 / CHOOSE A KEEPSAKE')
                ui.label('Your Common finds').classes('pw-subtitle')
                ui.input('Find an offering',value=well.search,on_change=lambda e:filter_changed('search',str(e.value or ''))).props('dense outlined clearable').classes('pw-search')
                with ui.element('div').classes('pw-filters'):
                    ui.select({'All tiers':'All tiers',**{tier:f'Tier {tier}' for tier in game.ITEM_BUCKETS}},value=well.tier,label='Tier',on_change=lambda e:filter_changed('tier',e.value)).props('dense outlined')
                    types = ['All types']+list(dict.fromkeys(game.saved_item_type_label(i) for i in player.inventory if i.rarity == 'Common'))
                    ui.select(types,value=well.kind if well.kind in types else 'All types',label='Type',on_change=lambda e:filter_changed('kind',e.value)).props('dense outlined')
                shelf()
            ritual()
            answer()
