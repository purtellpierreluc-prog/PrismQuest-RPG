"""A tactile three-part workbench: offerings, ritual, honest outcome forecast."""

import json

from nicegui import ui

from .crucible import CrucibleError, workbench_for
from .experience import item_visual_style
from .experience_ui import eyebrow, text
from .transactions import DesktopTransactionError


def render_crucible(state, game, actions):
    bench = workbench_for(state, game)

    def redraw():
        offerings.refresh()
        ritual.refresh()
        outcome.refresh()

    def choose(item):
        try:
            bench.choose(item)
            bench.error = False
        except CrucibleError as exc:
            bench.message, bench.error = str(exc), True
        redraw()

    def target(which):
        try:
            bench.set_target(which)
            bench.detail = 'forecast'
        except CrucibleError as exc:
            bench.message, bench.error = str(exc), True
        redraw()

    def clear(which=None):
        bench.clear(which)
        redraw()

    def confirm():
        try:
            bench.arm()
            bench.message, bench.error = '', False
        except CrucibleError as exc:
            bench.message, bench.error = str(exc), True
        ritual.refresh()

    def commit():
        try:
            bench.commit()
        except (CrucibleError, DesktopTransactionError) as exc:
            bench.message, bench.error = str(exc), True
        actions['refresh']()

    def item_icon(item, classes=''):
        uri = game.item_icon_uri(item) if item else ''
        if uri:
            ui.html(f'<img class="pc-item-icon {classes}" src="{text(uri)}" alt="" decoding="async" draggable="false">')
        else:
            ui.html('<span class="pc-empty-glyph" aria-hidden="true">+</span>')

    def inspect_props(item, key):
        return f'data-pd-inspect-key="crucible-{key}-{id(item)}"'

    def hover_contents(item):
        return '<span class="pd-inspect-content" hidden>' + game.build_item_hover_tooltip_html(item) + '</span>'

    @ui.refreshable
    def offerings():
        refs = state.get_transmute_item_refs()
        positions = {id(item): index for index, item in enumerate(state.player.inventory)}
        eligible = [item for _, _, item in refs if state.transmute_item_is_eligible(item)]
        tier_counts = {}
        for item in eligible:
            tier = game.item_required_level(item)
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        first = bench.first if bench.owns(bench.first) else None
        rows = [item for item in eligible if (bench.tier == 'All tiers' or f'Tier {game.item_required_level(item)}' == bench.tier)
                and (bench.rarity == 'All rarities' or item.rarity == bench.rarity)
                and bench.search.casefold() in (game.safe_item_name(item) + ' ' + item.subtype).casefold()]
        if bench.target == 'fuel' and first:
            rows = [item for item in rows if state.transmute_items_match(first, item)]
        with ui.element('div').classes('pc-offering-summary'):
            ui.label(f'{len(rows)} SHOWN / {len(eligible)} ELIGIBLE').classes('pd-comparison-note')
            ui.label(f'Choose a Tier {game.item_required_level(first)} sacrifice' if first and bench.target == 'fuel' else 'Choose the type you want to keep').classes('pc-list-purpose')
        with ui.element('div').classes('pc-library-scroll').props('aria-label="Available offerings"'):
            if not rows:
                with ui.element('div').classes('pc-empty-library'):
                    ui.label('Nothing for the fire.').classes('pc-section-title')
                    ui.label('Clear the filters, or bring two Fine-or-better items of the same tier. Common items are never consumed here.').classes('pd-subtle')
                    ui.button('Clear Filters', on_click=reset_filters).classes('mq-btn-secondary')
            for item in rows:
                selected = item is bench.first or item is bench.second
                compatible = item is not first if bench.target == 'fuel' else tier_counts[game.item_required_level(item)] >= 2
                fresh = bench.receipt is not None and item is bench.receipt.owned_item and bench.detail == 'result'
                badge = 'FORM' if item is bench.first else 'SACRIFICE' if item is bench.second else item.rarity.upper()
                with ui.button(on_click=lambda candidate=item: choose(candidate)).classes('pc-offering' + (' chosen' if selected else '') + (' pc-new-forged' if fresh else '')).style(item_visual_style(item, game)).props(
                        f'aria-label="{text("Offer " + game.safe_item_name(item) + ", Tier " + str(game.item_required_level(item)))}" data-pc-item="{id(item)}" data-pc-index="{positions[id(item)]}" aria-pressed={str(selected).lower()} ' + inspect_props(item, 'library')) as row:
                    row.set_enabled(compatible)
                    if fresh:
                        row._props['data-pc-forged'] = f'{bench.session}:{bench.receipt.serial}'
                    uri = game.item_icon_uri(item)
                    ui.html(f'<span class="pc-offering-art"><img src="{text(uri)}" alt="" decoding="async"></span>'
                            f'<span class="pc-offering-copy"><small>{text(badge)} / T{game.item_required_level(item)}</small><b>{text(game.equipped_item_display_name(item))}</b>'
                            f'<span>{text(game.safe_item_affix_preview_text(item))}</span>'
                            f'{"<em>Needs another item of this tier</em>" if not compatible and item is not first else ""}</span>' + hover_contents(item))

    def slot(which, title, subtitle, item, consumed=False):
        active = bench.target == which and not consumed
        with ui.element('div').classes('pc-offering-slot ' + which + (' active' if active else '') + (' consumed' if consumed else '')).style(item_visual_style(item, game)):
            with ui.button(on_click=lambda: target(which)).classes('pc-slot-select').props(f'aria-label="Choose {title.lower()}" ' + (inspect_props(item, which) if item else '')):
                ui.label(('01' if which == 'form' else '02') + ' / ' + title.upper()).classes('pc-slot-heading')
                item_icon(item)
                ui.label(game.equipped_item_display_name(item) if item else 'Choose an item').classes('pc-slot-name')
                ui.label(('CONSUMED' if consumed else item.rarity.upper()) + f' / TIER {game.item_required_level(item)}' if item else subtitle).classes('pc-slot-note')
                if item:
                    ui.html(hover_contents(item))
            if item and not consumed:
                ui.button(icon='close', on_click=lambda: clear(which)).props(f'aria-label="Remove {title.lower()}" dense flat').classes('pc-remove-slot')

    @ui.refreshable
    def ritual():
        quote = bench.quote()
        first, second = (bench.first if bench.owns(bench.first) else None), (bench.second if bench.owns(bench.second) else None)
        sealed = bench.detail == 'result' and bench.receipt is not None and first is None
        if sealed:
            first, second = bench.receipt.first, bench.receipt.second
        eyebrow('02 / THE RITUAL')
        ui.label('Keep the form.\nReforge the future.').classes('pc-ritual-title')
        with ui.element('div').classes('pc-offering-slots'):
            slot('form', 'Form', 'Defines type & tier', first, sealed)
            slot('fuel', 'Sacrifice', 'Any type / same tier', second, sealed)
        with ui.element('div').classes('pc-ritual-stage'):
            art = game.get_transmutation_scene_data_uri()
            ui.html(f'<img class="pc-sanctum-art" src="{text(art)}" alt="" decoding="async" draggable="false">'
                    '<div class="pc-orbit" aria-hidden="true"><i></i><i></i><i></i><span>&#9670;</span></div>'
                    '<div class="pc-convergence" aria-hidden="true"></div>')
            with ui.element('div').classes('pc-stage-copy'):
                ui.label('The fire has spoken.' if sealed else 'The form endures.' if first and second else 'Two offerings. One new possibility.').classes('pc-stage-title')
                ui.label('Your result is already saved.' if sealed else 'Every affix is rolled anew. Nothing is guaranteed to be stronger.').classes('pc-stage-caption')
        with ui.element('div').classes('pc-commit-zone').props('aria-live=polite'):
            if bench.message:
                ui.label(bench.message).classes('pc-status error' if bench.error else 'pc-status')
            if sealed:
                ui.label(f'{bench.receipt.cost} gold paid / two offerings consumed').classes('pc-cost-receipt')
                ui.button('Prepare Another Ritual', icon='add', on_click=lambda: clear()).classes('mq-btn-gold pc-commit')
            elif bench.armed and not quote.blocker:
                with ui.element('div').classes('pc-confirmation'):
                    ui.label('These two offerings will be consumed.').classes('pc-confirm-title')
                    ui.label(f'{game.equipped_item_display_name(first)} + {game.equipped_item_display_name(second)}').classes('pd-comparison-note')
                    with ui.element('div').classes('pc-confirm-actions'):
                        ui.button('Keep Choosing', on_click=lambda: (setattr(bench, 'armed', None), ritual.refresh())).classes('mq-btn-secondary')
                        ui.button(f'Confirm Transmutation / {quote.cost}g', on_click=commit).classes('mq-btn-gold pc-confirm-commit')
            else:
                with ui.element('div').classes('pc-fee'):
                    ui.label('RITUAL COST').classes('pd-eyebrow')
                    ui.label(f'{quote.cost} gold' if quote.cost else 'Choose both offerings').classes('pc-fee-amount')
                if quote.cost:
                    ui.label(f'2g base + {state.transmute_affix_count(first)}g form + {state.transmute_affix_count(second)}g sacrifice / {state.player.gold - quote.cost:,}g remaining').classes('pd-comparison-note')
                caption = f'Need {quote.cost} gold' if quote.cost > state.player.gold else 'Review Transmutation' if not quote.blocker else 'Choose Your Offerings'
                button = ui.button(caption, icon='auto_fix_high', on_click=confirm).classes('mq-btn-gold pc-commit')
                button.set_enabled(not quote.blocker)
                ui.label(quote.blocker or 'Both items are consumed. Review before committing.').classes('pc-commit-note')

    @ui.refreshable
    def outcome():
        quote = bench.quote()
        with ui.element('div').classes('pc-outcome-tabs'):
            ui.button('Forecast', on_click=lambda: (setattr(bench, 'detail', 'forecast'), ritual.refresh(), outcome.refresh())).classes('pc-tab' + (' selected' if bench.detail == 'forecast' else ''))
            if bench.receipt:
                ui.button('Last Result', on_click=lambda: (setattr(bench, 'detail', 'result'), ritual.refresh(), outcome.refresh())).classes('pc-tab' + (' selected' if bench.detail == 'result' else ''))
        if bench.detail == 'result' and bench.receipt:
            receipt = bench.receipt
            item = receipt.item
            signal = {'key': f'{bench.session}:{receipt.serial}', 'rarity': item.rarity,
                      'rank': game.RARITY_ORDER.index(item.rarity),
                      'up': receipt.rarity_delta > 0, 'reduced': bool(state.accessibility_reduce_motion or state.disable_last_drop_animation)}
            with ui.element('article').classes('pc-result').style(item_visual_style(item, game)) as result:
                result._props['data-pc-result'] = json.dumps(signal, separators=(',', ':'))
                eyebrow('03 / ' + ('RARITY ASCENDED' if receipt.rarity_delta > 0 else 'A DIFFERENT FATE' if receipt.rarity_delta < 0 else 'FRESHLY REFORGED'))
                with ui.element('div').classes('pc-result-crown'):
                    item_icon(item)
                    ui.label(item.rarity.upper()).classes('pc-result-rarity')
                    ui.label(game.equipped_item_display_name(item)).classes('pc-result-name').props('role=heading aria-level=2 tabindex=-1')
                    ui.label(f'TIER {game.item_required_level(item)} / {item.subtype}').classes('pc-result-tier')
                with ui.element('div').classes('pc-result-stats'):
                    ui.html(game.inventory_base_detail_html(item))
                    ui.label('NEW AFFIXES').classes('pd-eyebrow')
                    ui.html(game.inventory_affix_detail_html(item))
                ui.label('Saved in your pack' if bench.owns(receipt.owned_item) else 'Ritual record / this item has since moved').classes('pc-result-location')
                ui.html('<button type="button" class="pc-skip" data-pc-skip>Skip reveal</button>')
            with ui.element('div').classes('pc-result-actions'):
                inspect = ui.button('Inspect in Inventory', icon='inventory_2', on_click=lambda: actions['review'](receipt.owned_item)).classes('mq-btn-secondary')
                inspect.set_enabled(bench.owns(receipt.owned_item))
                again = ui.button('Use as Next Form', on_click=lambda: (bench.set_target('form'), choose(receipt.owned_item))).classes('mq-btn-gold')
                again.set_enabled(bench.owns(receipt.owned_item))
            return
        eyebrow('03 / THE POSSIBILITIES')
        if bench.owns(bench.first):
            item = bench.first
            with ui.element('div').classes('pc-projected-form').style(item_visual_style(item, game)):
                item_icon(item)
                ui.label(f'Tier {game.item_required_level(item)} {game.saved_item_type_label(item)}').classes('pc-projected-type')
                ui.label('TYPE & TIER GUARANTEED').classes('pd-comparison-note')
        else:
            ui.label('Choose what survives.').classes('pc-section-title')
            ui.label('Your first offering decides the item type and tier. The second feeds the fire.').classes('pd-subtle')
        if quote.outcomes:
            with ui.element('div').classes('pc-odds'):
                for chance in quote.outcomes:
                    color = game.RARITY_COLORS.get(chance.rarity, '#c6c5b6')
                    ui.html(f'<div class="pc-chance" style="--pc-chance:{text(color)}"><div><b>{text(chance.rarity)}</b><strong>{chance.percent}%</strong></div>'
                            f'<span class="pc-chance-track"><i style="width:{chance.percent}%"></i></span></div>')
            ui.label('Actual probabilities. Matching outcomes are combined.').classes('pd-comparison-note')
        else:
            with ui.element('div').classes('pc-how-it-works'):
                for number, title, detail in [('01', 'Keep a silhouette', 'Axe in the Form slot? An axe comes back.'),
                                               ('02', 'Match the tier', 'Fine or better. The sacrifice can be any item type.'),
                                               ('03', 'Meet your new roll', 'Rarity is weighted. Every affix is freshly rolled.')]:
                    ui.html(f'<div><span>{number}</span><b>{title}</b><p>{detail}</p></div>')
        ui.label('Rarity can rise, hold, or fall. The crucible never promises a power upgrade.').classes('pc-risk-note')
        ui.label('VARKESH / MASTER OF BRASS & CINDERS').classes('pd-eyebrow pc-maker')

    def reset_filters():
        bench.tier, bench.rarity, bench.search = 'All tiers', 'All rarities', ''
        tier.set_value(bench.tier)
        rarity.set_value(bench.rarity)
        search.set_value('')
        offerings.refresh()

    def filter_changed(key, value):
        setattr(bench, key, value or '')
        offerings.refresh()

    with ui.element('section').classes('pc-workspace'):
        with ui.element('aside').classes('pc-library'):
            eyebrow('01 / YOUR OFFERINGS')
            ui.label('Choose with intention.').classes('pc-library-title')
            ui.label('Pack items only. Equipped, saved and vaulted gear stay untouched.').classes('pc-library-note')
            search = ui.input('Find an offering', value=bench.search, placeholder='Name or item type').props('outlined dense debounce=200 clearable').classes('pc-search')
            search.on_value_change(lambda e: filter_changed('search', e.value))
            with ui.element('div').classes('pc-filters'):
                tier = ui.select(game.TRANSMUTE_TIER_FILTER_OPTIONS, label='Tier', value=bench.tier).props('outlined dense options-dense popup-content-class=pc-filter-popup')
                rarity = ui.select(game.TRANSMUTE_RARITY_FILTER_OPTIONS, label='Rarity', value=bench.rarity).props('outlined dense options-dense popup-content-class=pc-filter-popup')
                tier.on_value_change(lambda e: filter_changed('tier', e.value or 'All tiers'))
                rarity.on_value_change(lambda e: filter_changed('rarity', e.value or 'All rarities'))
            offerings()
        with ui.element('div').classes('pc-bench'):
            ritual()
        with ui.element('aside').classes('pc-outcome'):
            outcome()
