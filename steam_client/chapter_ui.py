"""A considered purchase, and a climb brought to its emotional conclusion."""

import json
import uuid

from nicegui import ui

from .chapters import ChapterError, ascension_for, market_for
from .experience import equipment_changes, item_visual_style, owned_item_index
from .experience_ui import eyebrow, image_plate, text
from .transactions import DesktopTransactionError


def render_market(state, game, actions):
    market = market_for(state, game)

    def select(offer):
        try:
            market.select(offer)
        except ChapterError as exc:
            market.message = str(exc)
        cards.refresh()
        details.refresh()

    def review():
        try:
            market.arm()
        except ChapterError as exc:
            market.message = str(exc)
        details.refresh()

    def purchase():
        try:
            market.buy()
            market.message = ''
        except (ChapterError, DesktopTransactionError) as exc:
            market.message = str(exc)
        actions['refresh']()

    @ui.refreshable
    def cards():
        for index, offer in enumerate(state.marketplace_offers):
            title, subtitle = [('The Essential', 'A modest, dependable curiosity'), ('The Collector', 'A rarer find, with a price to match'), ('The Wildcard', 'An unusual roll outside the ordinary')][index]
            item = offer.item
            selected = market.selected is offer
            with ui.button(on_click=lambda candidate=offer: select(candidate)).classes('pm-offer' + (' selected' if selected else '') + (' sold' if offer.sold else '')).style(item_visual_style(item, game)).props(f'aria-label="Inspect {title}" aria-pressed={str(selected).lower()} data-pm-offer={index}'):
                ui.html(f'<span class="pm-stall"><small>0{index+1} / {text(title.upper())}</small><span>{text(subtitle)}</span></span>'
                        f'<span class="pm-object"><img src="{text(game.item_icon_uri(item))}" alt="" draggable="false" decoding="async"></span>'
                        f'<span class="pm-offer-rarity">{text(item.rarity.upper())} / TIER {game.item_required_level(item)}</span>'
                        f'<b class="pm-offer-name">{text(game.equipped_item_display_name(item))}</b>'
                        f'<span class="pm-offer-affixes">{text(game.safe_item_affix_preview_text(item))}</span>'
                        f'<span class="pm-offer-price">{"ACQUIRED" if offer.sold else f"{offer.price:,} gold"}</span>')

    @ui.refreshable
    def details():
        offer = market.selected if any(o is market.selected for o in state.marketplace_offers) else None
        with ui.element('section').classes('pm-inspection'):
            if offer is None:
                with ui.element('div').classes('pm-empty-inspection'):
                    eyebrow('LOOK CLOSELY. CHOOSE DELIBERATELY.')
                    ui.label('What belongs in your next chapter?').classes('pm-inspection-title')
                    ui.label('Select a curio above. Inspect every affix, compare it to your equipped gear, then decide. A purchase never equips or replaces anything automatically.').classes('pd-subtle')
                return
            item = offer.item
            receipt = market.receipt
            if receipt and receipt.owned_item is item and offer.sold:
                with ui.element('div').classes('pm-receipt').props('role=status') as acquired:
                    acquired._props['data-pm-receipt'] = json.dumps({'key':receipt.key,'rarity':item.rarity,'reduced':bool(state.accessibility_reduce_motion or state.disable_last_drop_animation)})
                    ui.label('ACQUIRED / ' + game.equipped_item_display_name(item)).classes('pd-eyebrow')
                    ui.label(f'{receipt.price:,} gold paid. Your item is safely in the pack.').classes('pd-subtle')
                    inspect = ui.button('Inspect Purchased Item', icon='inventory_2', on_click=lambda: actions['review'](receipt.owned_item)).classes('mq-btn-secondary')
                    inspect.set_enabled(owned_item_index(state.player, receipt.owned_item) is not None)
            with ui.element('div').classes('pm-inspector-grid'):
                with ui.element('div').classes('pm-item-sheet').style(item_visual_style(item, game)):
                    eyebrow('THE CURIO / ' + item.rarity.upper())
                    ui.label(game.equipped_item_display_name(item)).classes('pm-inspection-title')
                    ui.html(game.inventory_base_detail_html(item))
                    ui.html(game.inventory_affix_detail_html(item))
                with ui.element('div').classes('pm-comparison'):
                    eyebrow('IF EQUIPPED / YOUR CURRENT BUILD')
                    reason, changes = equipment_changes(state.player, item, game.can_player_equip_item)
                    if reason:
                        ui.label('Not usable by this hero right now.').classes('pm-verdict')
                        ui.label(reason).classes('pd-subtle')
                        ui.label('You may still buy it and keep it for a later build.').classes('pd-comparison-note')
                    elif not changes:
                        ui.label('No change to the tracked combat stats.').classes('pd-subtle')
                        ui.label('Compare affixes for effects outside these totals.').classes('pd-comparison-note')
                    else:
                        ui.label('Real stat changes, with your proficiency included.').classes('pd-comparison-note')
                        for change in changes:
                            ui.html(f'<div class="pm-delta"><span>{text(change.label)}</span><b>{text(change.formatted(change.before))} &gt; {text(change.formatted(change.after))}</b>'
                                    f'<strong class="{"positive" if change.delta>0 else "negative"}">{"+" if change.delta>0 else "-"}{text(change.formatted(abs(change.delta)))}</strong></div>')
                    ui.label('Trade-offs are shown honestly. There is no invented gear score.').classes('pd-comparison-note')
            with ui.element('div').classes('pm-purchase'):
                if market.message:
                    ui.label(market.message).classes('pm-error').props('role=alert')
                blocker = market.blocker()
                if market.armed and not blocker:
                    ui.label(f'Buy {game.equipped_item_display_name(item)} for {offer.price:,} gold?').classes('pm-confirm-copy')
                    ui.button('Keep Browsing', on_click=lambda: (setattr(market, 'armed', None), details.refresh())).classes('mq-btn-secondary')
                    ui.button('Confirm Purchase', on_click=purchase).classes('mq-btn-gold')
                else:
                    with ui.element('div'):
                        ui.label(blocker or f'{state.player.gold-offer.price:,} gold will remain. Delivered to your pack, not equipped.').classes('pd-subtle')
                        ui.label('This stall stays sold until the next stock milestone.').classes('pd-comparison-note')
                    buy = ui.button(f'Review Purchase / {offer.price:,}g' if not offer.sold else 'Acquired', icon='shopping_bag', on_click=review).classes('mq-btn-gold')
                    buy.set_enabled(not blocker)

    with ui.element('section').classes('pm-workspace'):
        with ui.element('header').classes('pm-intro'):
            image_plate(game.get_marketplace_scene_data_uri(), 'Liora and Senna at the Marketplace', 'pm-merchant-art')
            with ui.element('div'):
                eyebrow('LIORA & SENNA / A SMALL COLLECTION OF POSSIBILITIES')
                ui.label('Three curiosities. Your next advantage.').classes('pm-title')
                ui.label('Inspect the piece. Understand the trade-off. Make it yours.').classes('pd-subtle')
            with ui.element('div').classes('pm-restock'):
                eyebrow('THE NEXT COLLECTION')
                level = state.get_next_marketplace_reroll_level()
                ui.label(f'Level {level}' if level else 'Final stock of this climb').classes('pm-restock-level')
                ui.label('Stock changes at level milestones, not on refresh.').classes('pd-comparison-note')
        with ui.element('div').classes('pm-offers'):
            cards()
        details()


def render_ascension(state, game, actions):
    rite = ascension_for(state, game)
    brief = rite.brief()
    client = ui.context.client

    def refresh():
        # Judgment outlives the button that submitted it. Schedule on the page,
        # never on a replaced button's slot or its refresh timer can be lost.
        with client:
            actions['refresh']()

    def enter():
        try:
            rite.enter()
        except (ChapterError, DesktopTransactionError) as exc:
            rite.error = str(exc)
        refresh()

    def select(key):
        try:
            rite.select(key)
            rite.error = ''
        except ChapterError as exc:
            rite.error = str(exc)
        refresh()

    async def submit(key):
        try:
            await rite.offer(key, refresh)
        except ChapterError as exc:
            rite.error = str(exc)
        refresh()

    def retreat():
        state.reset_masterquest_scene_state()
        rite.started = False
        rite.session = uuid.uuid4().hex
        state.enter_town()
        refresh()

    with ui.element('section').classes('ps-scene') as scene:
        scene._props['data-ps-signal'] = json.dumps(rite.signal(), separators=(',', ':'))
        if not rite.started:
            with ui.element('div').classes('ps-threshold-art'):
                ui.html(f'<img class="ps-prism" src="{text(game.get_masterquest_prism_data_uri())}" alt="The black prism" decoding="async">'
                        '<div class="ps-halo" aria-hidden="true"></div>')
                with ui.element('div').classes('ps-threshold-poem'):
                    eyebrow('THE CULMINATION OF YOUR CLIMB')
                    ui.label('You have carried\nthis light far.').classes('ps-title')
                    ui.label('Beyond the prism, a new legend waits.').classes('ps-poem')
                    ui.label(f'{state.player.name} / {state.player.player_class} / Level {state.player.level} / {state.player.wins:,} victories').classes('ps-champion-line')
            with ui.element('aside').classes('ps-threshold-brief'):
                with ui.element('div').classes('ps-threshold-reading'):
                    eyebrow('PRISMATIC QUEST / THE THRESHOLD')
                    ui.label('One last uncertainty.').classes('ps-section-title')
                    with ui.element('div').classes('ps-path'):
                        image_plate(game._hero_data_uri(state.player.player_class), state.player.player_class)
                        ui.label('>').classes('ps-path-arrow')
                        if brief['next']:
                            image_plate(game._hero_data_uri(brief['next']), brief['next'])
                        else:
                            image_plate(game.get_masterquest_prism_data_uri(), 'Final victory')
                    ui.label(brief['next'] or 'Complete the full class path').classes('ps-destination')
                    ui.html(f'<div class="ps-stakes"><span><small>VESSELS</small><b>{brief["count"]}</b></span><span><small>BLIND CLEAR</small><b>{text(brief["odds"])}</b></span><span><small>ENTRY</small><b>{brief["cost"]}g</b></span></div>')
                    ui.label('Each light belongs to one hidden vessel. This is blind matching, not a color puzzle. One wrong offering ends the attempt.').classes('ps-risk')
                    with ui.expansion('What happens to this hero?', value=True).classes('ps-carryover'):
                        ui.label('Final success preserves this hero. A failed attempt ends this climb.' if brief['final'] else 'Win or lose, this hero\'s climb ends. A successful rite also unlocks the next class.').classes('ps-consequence')
                        ui.label('Remaining gold, pack items and proficiency carry forward. Equipped gear routes to your saved sets or pack. Your vault, saved gear, companions and other chronicles remain intact.').classes('pd-subtle')
                    if rite.error or brief['blocker']:
                        ui.label(rite.error or brief['blocker']).classes('ps-error').props('role=alert')
                if getattr(rite, 'reviewed', False):
                    ui.label('You are committing this climb to the rite. Entry is paid now and is not refunded if you retreat.').classes('ps-confirmation')
                    with ui.element('div').classes('ps-entry-actions'):
                        ui.button('Not Yet', on_click=lambda: (setattr(rite, 'reviewed', False), refresh())).classes('mq-btn-secondary')
                        begin = ui.button(f'Enter the Rite / {brief["cost"]}g', on_click=enter).classes('mq-btn-gold')
                        begin.set_enabled(not brief['blocker'])
                else:
                    begin = ui.button('Review the Rite', icon='flare', on_click=lambda: (setattr(rite, 'reviewed', True), refresh())).classes('mq-btn-gold ps-primary')
                    begin.set_enabled(not brief['blocker'])
                ui.button('Keep Climbing', icon='arrow_back', on_click=actions['town']).classes('mq-btn-secondary')
            return
        with ui.element('header').classes('ps-rite-header'):
            with ui.element('div'):
                eyebrow('THE RITE / ONE LIGHT AT A TIME')
                ui.label('Let the silence answer.').classes('ps-section-title')
            ui.label(f'{len(state.masterquest_matched_essences)} / {len(state.masterquest_essence_order)} LIGHTS BOUND').classes('ps-bound-count')
        with ui.element('div').classes('ps-ritual-layout'):
            with ui.element('aside').classes('ps-ritual-guide'):
                image_plate(game._hero_data_uri(state.player.player_class), state.player.player_class, 'ps-current-hero')
                ui.label(state.player.name).classes('ps-section-title')
                ui.label(state.player.player_class).classes('pd-subtle')
                eyebrow('THE PROMISE')
                ui.label(brief['next'] or 'Final victory').classes('ps-destination')
                ui.label('Select a light, then offer it to a vessel. You can also drag the light. Colors and positions do not reveal the hidden pairing.').classes('pd-subtle')
                ui.label(f'Entry paid / {brief["cost"]}g').classes('ps-entry-paid')
                if rite.pending_verdict is not None:
                    ui.label(rite.error).classes('ps-error')
                    def retry():
                        try:
                            rite.retry_settlement()
                        except (ChapterError, DesktopTransactionError) as exc:
                            rite.error = str(exc)
                        refresh()
                    ui.button('Retry Saving Outcome', on_click=retry).classes('mq-btn-gold')
                elif not rite.busy:
                    if getattr(rite, 'want_leave', False):
                        ui.label('Leave the unfinished rite? Entry is not refunded; this hero can keep climbing.').classes('ps-risk')
                        ui.button('Stay', on_click=lambda: (setattr(rite, 'want_leave', False), refresh())).classes('mq-btn-secondary')
                        ui.button('Leave Unfinished Rite', on_click=retreat).classes('mq-btn-secondary')
                    else:
                        ui.button('Step Away', on_click=lambda: (setattr(rite, 'want_leave', True), refresh())).classes('mq-btn-secondary')
            with ui.element('div').classes('ps-chamber'):
                with ui.element('div').classes('ps-vessels').props('role=group aria-label="Hidden vessels"'):
                    for key in state.masterquest_container_order:
                        matched = key in state.masterquest_matched_containers
                        number = game.MASTERQUEST_VESSEL_KEYS.index(key)+1
                        button = ui.button(on_click=lambda vessel=key: submit(vessel)).classes('ps-vessel' + (' bound' if matched else '')).props(f'data-ps-vessel={key} aria-label="Offer to vessel {number}"')
                        with button:
                            ui.html(f'<span class="ps-vessel-rune" aria-hidden="true">{number:02}</span><span class="ps-vessel-bowl" aria-hidden="true"></span><b>{"BOUND" if matched else "VESSEL " + str(number)}</b>')
                        button.on('dragover', js_handler='event => event.preventDefault()')
                        button.on('drop', lambda _e, vessel=key: submit(vessel))
                        button.set_enabled(not matched and not rite.busy and rite.pending_verdict is None)
                with ui.element('div').classes('ps-prism-stage'):
                    ui.html(f'<img class="ps-prism" src="{text(game.get_masterquest_prism_data_uri())}" alt="The prism weighs the offering" decoding="async"><div class="ps-halo" aria-hidden="true"></div><div class="ps-prism-trace" aria-hidden="true"></div>')
                    phase = rite.signal()['phase']
                    heading = 'The chamber holds its breath.' if phase == 'judging' else 'The light found a home.' if phase == 'matched' else 'The silence breaks.' if phase == 'rejected' else 'Choose a light. Choose a vessel.'
                    ui.label(heading).classes('ps-chamber-caption').props('role=status')
                with ui.element('div').classes('ps-essences').props('role=group aria-label="Unbound lights"'):
                    for key in state.masterquest_essence_order:
                        matched = key in state.masterquest_matched_essences
                        number = game.MASTERQUEST_ESSENCE_KEYS.index(key)+1
                        selected = state.masterquest_active_essence() == key
                        button = ui.button(on_click=lambda essence=key: select(essence)).classes('ps-essence' + (' selected' if selected else '') + (' bound' if matched else '')).props(f'data-ps-essence={key} draggable=true aria-label="Select light {number}" aria-pressed={str(selected).lower()}')
                        with button:
                            ui.html(f'<img src="{text(state.masterquest_essence_visuals.get(key,""))}" alt="" decoding="async" draggable="false"><b>{"BOUND" if matched else "LIGHT " + str(number)}</b>')
                        button.on('dragstart', lambda _e, essence=key: state.start_masterquest_drag(essence))
                        button.on('dragend', lambda: state.clear_masterquest_drag())
                        button.set_enabled(not matched and not rite.busy and rite.pending_verdict is None)
                ui.label(rite.error or 'Each vessel is unique. One mistake ends the rite. The colors are not clues.').classes('ps-chamber-note')


def render_aftermath(state, game, actions):
    rite = state._desktop_ascension
    receipt = rite.receipt
    signal = rite.signal()
    def continue_climb(destination=None):
        rite.acknowledge()
        if receipt.final:
            if destination == 'labyrinth':
                actions['route']('labyrinth')
            else:
                state.enter_town()
                actions['refresh']()
        else:
            actions['refresh']()
    with ui.element('main').classes('ps-aftermath ' + ('victory' if receipt.passed else 'failure')) as result:
        result._props['data-ps-signal'] = json.dumps(signal,separators=(',', ':'))
        with ui.element('header').classes('ps-aftermath-header'):
            eyebrow('PRISMQUEST / A CHAPTER WRITTEN IN LIGHT')
            ui.label('PRISMATIC QUEST').classes('ps-wordmark')
        with ui.element('div').classes('ps-aftermath-body'):
            with ui.element('section').classes('ps-aftermath-art'):
                image_plate(game._hero_data_uri(receipt.player_class), 'The hero who carried this climb', 'ps-legacy-hero')
                ui.html('<div class="ps-aftermath-orbit" aria-hidden="true"></div><div class="ps-aftermath-ray" aria-hidden="true"></div>')
                ui.label(receipt.name).classes('ps-legacy-name')
                ui.label(receipt.player_class + ' / LEVEL ' + str(receipt.level)).classes('ps-champion-line')
            with ui.element('section').classes('ps-aftermath-copy'):
                with ui.element('div').classes('ps-aftermath-reading'):
                    eyebrow('THE FULL PATH, COMPLETED' if receipt.final else 'A NEW LEGEND, UNLOCKED' if receipt.passed else 'THE LIGHT WENT QUIET')
                    ui.label('You became\nthe light.' if receipt.final else 'The prism\nremembers you.' if receipt.passed else 'The climb\nstill mattered.').classes('ps-outcome-title').props('role=heading aria-level=1 tabindex=-1')
                    ui.label('The whole class path stands behind you. Your hero remains; the Labyrinth still calls.' if receipt.final else f'{receipt.next_class} is now yours to begin. This chapter ends, but what you carried through it remains.' if receipt.passed else 'The prism refused the offering, not the story. This attempt is recorded. Your remaining gold, gear and proficiency carry into the next climb.').classes('ps-outcome-story')
                    with ui.element('div').classes('ps-legacy-facts'):
                        for title, value in [('VICTORIES',f'{receipt.victories:,}'),('TIME ON THIS CLIMB',game.format_duration(receipt.seconds)),('CLASS ATTEMPTS',str(receipt.attempts))]:
                            ui.html(f'<span><small>{text(title)}</small><b>{text(value)}</b></span>')
                    with ui.element('div').classes('ps-what-endures'):
                        eyebrow('WHAT ENDURES')
                        ui.label(f'{receipt.gold:,} gold / {receipt.items} pack items / {receipt.companions} permanent companions').classes('ps-kept')
                        ui.label('Your vault, saved sets, proficiency and other chronicles are preserved. Equipped gear follows the existing carryover rules.').classes('pd-subtle')
                ui.button('Return Victorious' if receipt.final else 'Choose Your Next Legend' if receipt.passed else 'Begin the Next Climb', icon='arrow_forward', on_click=continue_climb).classes('mq-btn-gold ps-aftermath-primary')
                if receipt.final:
                    ui.button('Continue into the Labyrinth', on_click=lambda: continue_climb('labyrinth')).classes('mq-btn-secondary')
