"""The Concourse: a bounded, decision-first home for shared adventures."""

from datetime import datetime

from nicegui import ui

from ..experience_ui import eyebrow, image_plate, inspect_item_html
from .service import RealmError

TABS = [('Expedition', 'explore'), ('Armory & Courier', 'inventory_2'), ('Bazaar', 'storefront'),
        ('Guild Hall', 'forum'), ('Realm Ladder', 'leaderboard')]


def render_concourse(controller, game, back):
    async def perform(operation, args=None):
        if controller.client.busy:
            return
        ui.run_javascript("document.querySelector('.pn-workspace')?.setAttribute('aria-busy','true')")
        try:
            result = await controller.client.command(operation, args)
            controller.message, controller.error = result['message'], False
        except (RealmError, ValueError) as exc:
            controller.message, controller.error = str(exc), True
        finally:
            ui.run_javascript("document.querySelector('.pn-workspace')?.setAttribute('aria-busy','false')")
        view.refresh()

    async def refresh():
        if not controller.client or controller.client.busy:
            return
        try:
            changed = await controller.client.refresh()
            if changed:
                view.refresh()
        except RealmError as exc:
            controller.message, controller.error = str(exc), True
            view.refresh()

    def action(title, operation, args=None, *, primary=False, enabled=True):
        btn = ui.button(title, on_click=lambda: perform(operation, args)).classes('mq-btn-gold' if primary else 'mq-btn-secondary')
        btn.set_enabled(enabled and not controller.client.busy and controller.client.pending is None)
        return btn

    def draft(key, title, default='', **kwargs):
        field = ui.input(title, value=controller.drafts.get(key, default), **kwargs).props('outlined dense').classes('pn-input')
        field.on_value_change(lambda event: controller.drafts.__setitem__(key, event.value or ''))
        return field

    def item_card(entry, extra=None):
        item = game.Item.from_dict(entry['item'])
        with ui.element('article').classes('pn-item'):
            ui.html(inspect_item_html(item, game, key='realm-item-' + entry['id'], caption=item.subtype))
            if extra:
                extra()

    def panel(title, detail=None):
        eyebrow(title)
        if detail:
            ui.label(detail).classes('pd-subtle')

    def empty(title, detail):
        with ui.element('div').classes('pn-empty'):
            ui.label(title).classes('pn-section-title')
            ui.label(detail).classes('pd-subtle')

    def party_view(data):
        party = data['party']
        if not party:
            with ui.element('div').classes('pn-two-columns'):
                with ui.element('section').classes('pn-panel pn-expedition-invite'):
                    panel('01 / THE LIGHT CALLS', 'Five adventurers. One shared expedition.')
                    ui.label('Gather your party.').classes('pn-display-title')
                    image_plate(game.get_town_scene_data_uri(), 'The Concourse', 'pn-concourse-art')
                    ui.label('Invite by code. Ready together. The leader navigates; the realm resolves every encounter once for the whole party.').classes('pd-subtle')
                    action('Open Expedition', 'party_create', primary=True, enabled=data['player']['level'] >= 45)
                    code = draft('party-code', 'Expedition invitation code', placeholder='LUX-...')
                    ui.button('Join Expedition', on_click=lambda: perform('party_join', {'code': code.value})).classes('mq-btn-secondary')
                    ui.label('Unlocks at level 45. Solo realm expeditions are welcome too.').classes('pd-comparison-note')
                with ui.element('section').classes('pn-panel'):
                    panel('02 / YOUR REALM JOURNEY', 'Separate from your solo chronicles. Nothing is uploaded from them.')
                    ui.label('Earn it here. Keep it here.').classes('pn-section-title')
                    action('Fight Realm Arena', 'arena', primary=True)
                    action('Recover at Realm Inn', 'recover')
                    ui.label('Arena encounters use your class, equipment and the existing combat rules. Results and drops are saved by the realm.').classes('pd-subtle')
                    if data['sandbox'] and not data['kit']:
                        ui.separator()
                        panel('SANDBOX SHORTCUT', 'Optional: level 45, common tier-45 gear, 2,000 test gold and four finds. Once per test character. These never enter a live economy.')
                        action('Prepare Test Character', 'test_kit')
                    panel('CLASS & EQUIPMENT', data['player']['player_class'])
                    for slot, raw in data['player']['equipped'].items():
                        if raw:
                            ui.html(inspect_item_html(game.Item.from_dict(raw), game, key='realm-loadout-' + slot, caption=slot))
            return
        checkpoint = party.get('checkpoint', {})
        session = checkpoint.get('session', {})
        status = session.get('status', 'lobby')
        lead = party['leader'] == data['user']
        with ui.element('div').classes('pn-party-heading'):
            ui.label('Labyrinth of Light').classes('pn-section-title')
            ui.label(party['code']).classes('pn-code')
            ui.label(f'{len(party["members"])}/5 / {status.upper()}').classes('pn-chip')
            ui.button('Leave Party', on_click=lambda: leave_confirmation()).classes('mq-btn-secondary')
        with ui.element('div').classes('pn-party-layout'):
            with ui.element('aside').classes('pn-party-members'):
                for profile in party['profiles']:
                    p = profile['player']
                    with ui.element('article').classes('pn-party-member'):
                        image_plate(game._hero_data_uri(p['player_class']), p['player_class'])
                        with ui.element('div'):
                            ui.label(profile['name']).classes('pn-member-name')
                            ui.label(f'{p["player_class"]} / {p["level"]}').classes('pd-comparison-note')
                            ui.html(f'<div class="pn-health" title="{p["hp"]:,} / {p["max_hp"]:,}"><i style="width:{100*max(0,p["hp"])/max(1,p["max_hp"]):.2f}%"></i></div>')
                            ui.html(f'<div class="pn-mana" title="{p["mana"]:,} / {p["max_mana"]:,}"><i style="width:{100*max(0,p["mana"])/max(1,p["max_mana"]):.2f}%"></i></div>')
                            if status == 'lobby':
                                ui.label('READY' if profile['id'] in party['ready'] else 'PREPARING').classes('pn-chip')
                            elif profile['id'] == data['user'] and status == 'exploring':
                                tank = next((row.get('tank', False) for row in checkpoint.get('members', []) if row['user_id'] == data['user']), False)
                                action('Tank ON' if tank else 'Tank OFF', 'party_tank', {'enabled': not tank})
                                action('Activate Ability', 'party_ability')
            with ui.element('section').classes('pn-panel pn-maze-panel'):
                if status == 'lobby':
                    empty('A shared road beyond sixty.', 'All members must be ready before the leader departs. Gear and trading lock during the expedition; earned rewards are kept if the party ends it.')
                    action('Not Ready' if data['user'] in party['ready'] else 'Ready Up', 'party_ready', primary=True)
                    if lead:
                        action('Enter the Labyrinth', 'party_start', primary=True, enabled=set(party['members']) == set(party['ready']))
                else:
                    tiles = session.get('tile_states', {})
                    cells = []
                    for y in range(7):
                        for x in range(7):
                            tile = tiles.get(f'{x},{y}', {})
                            current = session.get('current_x') == x and session.get('current_y') == y
                            cells.append(f'<span class="pn-tile {"visited" if tile.get("visited") else ""} {"current" if current else ""}" aria-label="{"Party position" if current else "Explored" if tile.get("visited") else "Unexplored"}">{"&#9670;" if current else "&#183;" if tile.get("visited") else ""}</span>')
                    ui.label(f'FLOOR {session.get("floor",1)} / {sum(bool(t.get("visited")) for t in tiles.values())}/49 EXPLORED').classes('pd-eyebrow')
                    ui.html('<div class="pn-maze">' + ''.join(cells) + '</div>')
                    if status == 'exploring':
                        with ui.element('div').classes('pn-directions'):
                            for title, direction in [('North', 'up'), ('West', 'left'), ('South', 'down'), ('East', 'right')]:
                                action(title, 'party_move', {'direction': direction}, enabled=lead)
                        ui.label('Leader controls movement.' if not lead else 'Every new tile is empty or an automatic encounter.').classes('pd-comparison-note')
                    elif status == 'reward':
                        panel('CHOOSE YOUR PRISM', 'Vote within 25 seconds. Majority wins; the leader breaks ties. The realm seals the vote on the next party update.')
                        for index, reward in enumerate(session.get('reward_options', [])):
                            action(reward.get('title', f'Prism {index+1}'), 'party_vote', {'choice': index})
                            for key in ('boon', 'bane'):
                                if reward.get(key):
                                    ui.label(reward[key]).classes('pd-subtle')
                    elif status == 'defeated':
                        empty('The light has taken its toll.', 'Your earned items and progression are preserved. Leave the party to recover and prepare again.')
                    logs = session.get('pending_encounter', {}).get('log', [])
                    if logs:
                        with ui.expansion('Last Encounter', value=False).classes('pn-battle-log'):
                            for line in logs[:12]:
                                ui.label(line).classes('pd-subtle')

    def leave_confirmation():
        with ui.dialog() as dialog, ui.card().classes('pn-confirm'):
            ui.label('Leave this party?').classes('pn-section-title')
            ui.label('An active expedition will end for everyone. Earned items and levels are kept. Disconnecting without leaving preserves the expedition.').classes('pd-subtle')
            ui.button('Keep Adventuring', on_click=dialog.close).classes('mq-btn-secondary')
            async def leave():
                dialog.close()
                await perform('party_leave')
            ui.button('Leave Party', on_click=leave).classes('mq-btn-gold')
        dialog.open()

    def armory(data):
        with ui.element('div').classes('pn-two-columns'):
            with ui.element('section').classes('pn-panel'):
                panel('REALM INVENTORY', 'Hover an item to inspect. Pack and vault belong only to this realm character.')
                location = ui.toggle({'pack': 'Pack', 'vault': 'Vault'}, value=controller.drafts.get('location', 'pack')).classes('pn-toggle')
                location.on_value_change(lambda e: (controller.drafts.__setitem__('location', e.value), view.refresh()))
                rows = [r for r in data['items'] if r['location'] == location.value]
                if not rows:
                    empty('Room for your next find.', 'Win realm Arena encounters, receive a courier delivery or purchase an item in the Bazaar.')
                for entry in rows:
                    def controls(row=entry):
                        with ui.element('div').classes('pn-item-actions'):
                            if row['location'] == 'pack':
                                action('Equip', 'equip', {'item': row['id']})
                            action('Deposit' if row['location'] == 'pack' else 'Withdraw', 'deposit' if row['location'] == 'pack' else 'withdraw', {'item': row['id']})
                            ui.button('Send', on_click=lambda r=row: send_dialog(r)).classes('mq-btn-secondary')
                            ui.button('List', on_click=lambda r=row: listing_dialog(r)).classes('mq-btn-secondary')
                    item_card(entry, controls)
            with ui.element('section').classes('pn-panel'):
                panel('YOUR VAULT ADDRESS', 'Share this realm-specific code to receive an item. Couriers cannot touch your solo inventory.')
                ui.label(data['code']).classes('pn-code')
                panel('INCOMING COURIERS')
                if not data['deliveries']:
                    empty('No incoming parcels.', 'Direct delivery, with no public listing to snipe.')
                for delivery in data['deliveries']:
                    item_card(delivery, lambda d=delivery: (ui.label('From ' + d['sender']).classes('pd-subtle'), action('Claim to Vault', 'claim', {'delivery': d['id']})))
                panel('CHARACTER GROWTH', f'{data["player"]["unspent_stat_points"]} points available')
                for stat in ('strength', 'dexterity', 'intelligence', 'vitality'):
                    action(f'+ {stat.title()}', 'allocate', {'stat': stat}, enabled=data['player']['unspent_stat_points'] > 0)

    def send_dialog(entry):
        with ui.dialog() as dialog, ui.card().classes('pn-confirm'):
            ui.label('Send a secure courier').classes('pn-section-title')
            ui.label(entry['item']['name']).classes('pd-subtle')
            code = ui.input('Recipient vault code', placeholder='PQ-...').props('outlined')
            ui.label('Check the code carefully. Sending is permanent and the item leaves your inventory immediately.').classes('pd-subtle')
            ui.button('Cancel', on_click=dialog.close).classes('mq-btn-secondary')
            async def send():
                dialog.close()
                await perform('send', {'item': entry['id'], 'code': code.value})
            ui.button('Confirm Send', on_click=send).classes('mq-btn-gold')
        dialog.open()

    def listing_dialog(entry=None, listing=None):
        with ui.dialog() as dialog, ui.card().classes('pn-confirm'):
            ui.label('Change Listing Price' if listing else 'Offer to the Bazaar').classes('pn-section-title')
            price = ui.number('Gold price', value=listing['price'] if listing else 100, min=1, max=1_000_000, precision=0).props('outlined')
            ui.label('Listed items are held in escrow until sold or cancelled. Purchases go to the buyer\'s realm vault.').classes('pd-subtle')
            ui.button('Cancel', on_click=dialog.close).classes('mq-btn-secondary')
            async def publish():
                value = price.value
                if value is None or int(value) != value:
                    ui.notify('Enter a whole-number gold price.', type='warning')
                    return
                dialog.close()
                await perform('reprice' if listing else 'list', {'price': int(value), **({'listing': listing['id']} if listing else {'item': entry['id']})})
            ui.button('Save Price' if listing else 'Create Listing', on_click=publish).classes('mq-btn-gold')
        dialog.open()

    def bazaar(data):
        mode = ui.toggle(['Browse', 'My Listings', 'Ledger'], value=controller.drafts.get('bazaar', 'Browse')).classes('pn-toggle')
        mode.on_value_change(lambda e: (controller.drafts.__setitem__('bazaar', e.value), view.refresh()))
        if mode.value == 'Ledger':
            panel('YOUR REALM LEDGER', 'Gold, counterpart and timestamp for every completed Bazaar trade and courier.')
            if not data['ledger']:
                empty('A clean first page.', 'Completed transactions will appear here.')
            for row in data['ledger']:
                stamp = datetime.fromtimestamp(row['created']).strftime('%b %d / %H:%M')
                with ui.element('article').classes('pn-ledger-row'):
                    ui.label(row['kind']).classes('pn-chip')
                    ui.label(row['item'])
                    ui.label(row['other'] or 'Realm').classes('pd-subtle')
                    ui.label(f'{row["gold"]:+,}g').classes('pd-item-value')
                    ui.label(stamp).classes('pd-comparison-note')
            return
        rows = [r for r in data['listings'] if (r['seller_id'] == data['user']) == (mode.value == 'My Listings')]
        with ui.element('div').classes('pn-market-filters'):
            rarity = ui.select(['All rarities', *game.RARITY_COLORS], value=controller.drafts.get('rarity', 'All rarities'), label='Rarity').props('outlined dense')
            kind = ui.select(['All types', 'weapon', 'armor', 'charm'], value=controller.drafts.get('kind', 'All types'), label='Item type').props('outlined dense')
            for field, key in [(rarity, 'rarity'), (kind, 'kind')]:
                field.on_value_change(lambda e, k=key: (controller.drafts.__setitem__(k, e.value), view.refresh()))
        rows = [r for r in rows if (rarity.value == 'All rarities' or r['item']['rarity'] == rarity.value) and (kind.value == 'All types' or r['item']['slot'] == kind.value)]
        if not rows:
            empty('No offers on this shelf.', 'Only real player listings appear here. List an item from Armory & Courier to get the market started.')
        with ui.element('div').classes('pn-market-grid'):
            for listing in rows:
                def controls(row=listing):
                    ui.label(f'{row["price"]:,} gold / {row["seller"]}').classes('pd-item-value')
                    if row['seller_id'] == data['user']:
                        ui.button('Change Price', on_click=lambda r=row: listing_dialog(listing=r)).classes('mq-btn-secondary')
                        action('Cancel Listing', 'cancel', {'listing': row['id']})
                    else:
                        ui.button('Purchase', on_click=lambda r=row: purchase_dialog(r)).classes('mq-btn-gold')
                item_card(listing, controls)

    def purchase_dialog(listing):
        with ui.dialog() as dialog, ui.card().classes('pn-confirm'):
            ui.label('Confirm purchase').classes('pn-section-title')
            ui.label(f'{listing["item"]["name"]} / {listing["price"]:,} gold').classes('pd-item-value')
            ui.button('Keep Browsing', on_click=dialog.close).classes('mq-btn-secondary')
            async def buy():
                dialog.close()
                await perform('buy', {'listing': listing['id'], 'expected_price': listing['price']})
            ui.button('Buy to Vault', on_click=buy).classes('mq-btn-gold')
        dialog.open()

    def guild_hall(data):
        with ui.element('div').classes('pn-two-columns'):
            with ui.element('section').classes('pn-panel'):
                guild = data['guild']
                if guild:
                    panel('YOUR GUILD', guild['name'])
                    ui.label(guild['code']).classes('pn-code')
                    for member in guild['members']:
                        ui.label(member['name'] + (' / Founder' if member['id'] == guild['leader'] else '')).classes('pn-member-name')
                    action('Leave Guild', 'guild_leave')
                else:
                    panel('BUILD SOMETHING TOGETHER', 'Found a guild or enter a private invitation code.')
                    name = draft('guild-name', 'Guild name')
                    ui.button('Found Guild', on_click=lambda: perform('guild_create', {'name': name.value})).classes('mq-btn-gold')
                    code = draft('guild-code', 'Guild invitation code', placeholder='G-...')
                    ui.button('Join Guild', on_click=lambda: perform('guild_join', {'code': code.value})).classes('mq-btn-secondary')
            with ui.element('section').classes('pn-panel'):
                channel = ui.toggle(['Town', 'Guild'] if guild else ['Town'], value=controller.drafts.get('chat-channel', 'Town') if guild else 'Town').classes('pn-toggle')
                channel.on_value_change(lambda e: (controller.drafts.__setitem__('chat-channel', e.value), view.refresh()))
                panel('THE COMMON ROOM', 'Private guild messages are only delivered to current members. Refresh when you want new messages; no background chat traffic.')
                with ui.element('div').classes('pn-messages'):
                    for message in data['messages']:
                        if (message['channel'] == 'town') != (channel.value == 'Town'):
                            continue
                        with ui.element('article').classes('pn-message'):
                            ui.label(message['name']).classes('pn-member-name')
                            ui.label(message['body']).classes('pd-subtle')
                body = draft('chat-body', 'Message', placeholder='Say something kind...')
                async def send():
                    value = body.value
                    controller.drafts['chat-body'] = ''
                    await perform('chat', {'body': value, 'channel': channel.value.lower()})
                ui.button('Send Message', on_click=send).classes('mq-btn-gold')

    def ladder(data):
        panel('REALM LADDER', 'Verified realm progression only. This is not the live browser-game ladder or a Steam leaderboard.')
        for rank, row in enumerate(data['ladder'], start=1):
            with ui.element('article').classes('pn-ledger-row pn-ladder-row'):
                ui.label(f'{rank:02}').classes('pd-item-value')
                ui.label(row['name']).classes('pn-member-name')
                ui.label(row['class']).classes('pd-subtle')
                ui.label(f'Level {row["level"]}').classes('pn-chip')
                ui.label(f'{row["wins"]:,} victories').classes('pd-comparison-note')

    @ui.refreshable
    def view():
        data = controller.client.data if controller.client else None
        with ui.element('main').classes('pn-workspace'):
            with ui.element('header').classes('pn-heading'):
                with ui.element('div'):
                    eyebrow('PRISMQUEST / THE CONCOURSE')
                    ui.label('A world worth sharing.').classes('pn-title')
                realm_label = 'SHARED TEST REALM / NOT STEAM' if controller.client and controller.client.url else 'LOCAL TEST REALM / NOT STEAM'
                ui.label(realm_label if not data or data['sandbox'] else 'STEAM-AUTHENTICATED REALM').classes('pn-status')
                ui.button('Return to Solo', icon='arrow_back', on_click=back).classes('mq-btn-secondary')
            if not data:
                with ui.element('div').classes('pn-entry'):
                    with ui.element('section').classes('pn-entry-hero'):
                        image_plate(game.get_town_scene_data_uri(), 'A gathering place at the edge of the light', 'pn-entry-art')
                        ui.label('Trade. Gather. Venture beyond.').classes('pn-display-title')
                        ui.label('The Bazaar, secure item couriers, guild halls and shared Labyrinth expeditions return in a separate realm. Your solo chronicles stay yours.').classes('pd-subtle')
                    with ui.element('section').classes('pn-panel pn-entry-form'):
                        panel('PLAY THE NETWORK PREVIEW', 'No Steam IDs yet? Use the local test realm. It persists on this machine and cannot affect the live game.')
                        name = draft('name', 'Realm character name', 'Prism Wanderer')
                        hero = ui.select(['Black Guard', 'Shadow Mage', 'Shadow Warrior', 'Night Angel'], value='Black Guard', label='Starting class').props('outlined')
                        async def enter():
                            try:
                                await controller.preview(name.value, hero.value)
                                controller.message, controller.error = 'Welcome to the Concourse. Solo chronicles were not changed.', False
                            except (RealmError, ValueError) as exc:
                                controller.message, controller.error = str(exc), True
                            view.refresh()
                        ui.button('Enter Test Realm', icon='public', on_click=enter).classes('mq-btn-gold')
                        def connect_dialog():
                            with ui.dialog() as dialog, ui.card().classes('pn-confirm'):
                                ui.label('Connect a developer test service').classes('pn-section-title')
                                ui.label('For multi-client testing on this machine. Start tools/run_realm_server.py first. This is not a Steam sign-in.').classes('pd-subtle')
                                url = ui.input('Test service URL', value='http://127.0.0.1:8766').props('outlined')
                                key = ui.input('Sandbox access key', password=True).props('outlined')
                                ui.button('Cancel', on_click=dialog.close).classes('mq-btn-secondary')
                                async def connect():
                                    try:
                                        await controller.test_service(url.value, key.value, name.value, hero.value)
                                        key.value = ''
                                        dialog.close()
                                        controller.message, controller.error = 'Connected to the shared developer test realm.', False
                                        view.refresh()
                                    except (RealmError, ValueError) as exc:
                                        ui.notify(str(exc), type='negative')
                                ui.button('Connect Test Service', on_click=connect).classes('mq-btn-gold')
                            dialog.open()
                        ui.button('Developer Test Service', on_click=connect_dialog).classes('mq-btn-secondary')
                        ui.separator()
                        panel('STEAM CONNECTION / NOT CONFIGURED', 'Live Steam play still needs your App ID, a native ticket bridge and a hosted realm. No publisher secrets belong in this game client.')
                        if controller.message:
                            ui.label(controller.message).classes('pn-notice error' if controller.error else 'pn-notice')
                return
            with ui.element('div').classes('pn-body'):
                with ui.element('aside').classes('pn-rail'):
                    p = data['player']
                    image_plate(game._hero_data_uri(p['player_class']), p['player_class'], 'pn-rail-portrait')
                    ui.label(data['name']).classes('pn-member-name')
                    ui.label(f'{p["player_class"]} / Level {p["level"]}').classes('pd-comparison-note')
                    ui.label(f'{p["gold"]:,} GOLD').classes('pn-gold')
                    for title, icon in TABS:
                        ui.button(title, icon=icon, on_click=lambda tab=title: (setattr(controller, 'tab', tab), view.refresh())).classes('pn-rail-button ' + ('selected' if title == controller.tab else '')).props('aria-pressed=' + str(title == controller.tab).lower())
                    ui.button('Refresh Realm', icon='sync', on_click=refresh).classes('mq-btn-secondary pn-refresh')
                    if controller.error:
                        async def reconnect():
                            try:
                                await controller.reconnect()
                                controller.error, controller.message = False, 'Reconnected. Realm progress restored.'
                            except RealmError as exc:
                                controller.message = str(exc)
                            view.refresh()
                        ui.button('Reconnect Realm', on_click=reconnect).classes('mq-btn-secondary')
                    ui.label('TEST DATA / SEPARATE SAVES' if data['sandbox'] else 'SERVER-OWNED PROGRESSION').classes('pd-comparison-note')
                with ui.element('div').classes('pn-main'):
                    if controller.message:
                        ui.label(controller.message).classes('pn-notice error' if controller.error else 'pn-notice')
                    if controller.client.pending:
                        ui.button('Retry Pending Action', on_click=lambda: perform(None)).classes('mq-btn-gold')
                    with ui.element('div').classes('pn-content'):
                        {'Expedition': party_view, 'Armory & Courier': armory, 'Bazaar': bazaar,
                         'Guild Hall': guild_hall, 'Realm Ladder': ladder}[controller.tab](data)
    view()
    # One low-frequency revision check, only while a party view is open. No UI
    # rerender when unchanged; fields/dialogs never have a polling parent.
    async def poll_party():
        client = controller.client
        if client and client.data and controller.tab == 'Expedition' and client.data['party'] and not client.busy and not controller.error:
            party = client.data['party']
            before = client.data['revision']
            if party.get('checkpoint', {}).get('session', {}).get('status') == 'reward':
                started = party['checkpoint']['session'].get('pending_encounter', {}).get('reward_vote_started_at')
                elapsed = (datetime.now().astimezone() - datetime.fromisoformat(started)).total_seconds() if started else 0
                if elapsed >= 25 and not client.pending:
                    try:
                        await client.command('party_refresh')
                    except RealmError:
                        pass
            try:
                await client.refresh()
                if client.data['revision'] != before:
                    view.refresh()
            except RealmError as exc:
                controller.message, controller.error = str(exc), True
                view.refresh()
    ui.timer(3, poll_party)
