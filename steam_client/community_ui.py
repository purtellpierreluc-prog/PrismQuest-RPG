"""The Bazaar, Guild Hall and Ladder belong to the hero's town, not a test hub."""

import json
import uuid
from datetime import datetime

from nicegui import ui

from .chapters import fingerprint
from .community import TownError, parse_price, town_for
from .experience import item_visual_style
from .experience_ui import eyebrow, image_plate, inspect_item_html, text
from .transactions import DesktopTransactionError


def date_label(value):
    try:
        return datetime.fromisoformat(value).astimezone().strftime('%b %d, %Y / %H:%M')
    except (ValueError,TypeError,AttributeError):
        return 'Date unavailable'


def receipt(town):
    if town.notice:
        node = ui.label(town.notice).classes('nt-notice'+(' error' if town.error else '')).props('role=status aria-live=polite')
        if town.receipt and not town.error:
            node._props['data-town-receipt'] = json.dumps(town.receipt)


def heading(kicker,title,detail):
    with ui.element('header').classes('nt-scene-header'):
        with ui.element('div'):
            eyebrow(kicker)
            ui.label(title).classes('nt-display')
        with ui.element('div').classes('nt-local-scope'):
            ui.label('LOCAL CHRONICLE').classes('nt-scope-badge')
            ui.label(detail).classes('nt-header-note')


def _perform(town,actions,operation,title):
    try:
        result = operation()
        town.notice,town.error = title,False
        town.receipt = {'key':uuid.uuid4().hex,'kind':'town','reduced':bool(town.state.accessibility_reduce_motion)}
        town.selected,town.armed = None,None
        actions['refresh']()
        return result
    except (TownError,DesktopTransactionError) as exc:
        town.notice,town.error,town.armed = str(exc),True,None
        actions['refresh']()
        return None


def render_bazaar(state,game,actions):
    town = town_for(state,game)
    town.enter('bazaar')
    view = town.view if town.view in {'Browse','Sell & Manage','Ledger'} else 'Browse'

    def switch(tab):
        town.view,town.selected,town.armed = tab,None,None
        actions['refresh']()

    def choose(kind,value):
        town.selected,town.armed = (kind,value),None
        if kind == 'listing':
            town.drafts['price'] = str(value['price'])
        listings.refresh()
        inspection.refresh()

    def changed(key,value):
        setattr(town,key,value or '')
        listings.refresh()

    def rows():
        if view == 'Ledger':
            return town.data()['ledger']
        entries = ([('pack',item) for item in state.player.inventory] if view == 'Sell & Manage' else [])
        entries += [('listing',row) for row in town.listings() if row['own'] == (view == 'Sell & Manage')]
        result = []
        for kind,value in entries:
            item = value if kind == 'pack' else game.Item.from_dict(value['item'])
            if (town.search.casefold() not in (item.name+' '+item.subtype).casefold()
                or (town.kind != 'All types' and game.saved_item_type_label(item) != town.kind)
                or (town.tier != 'All tiers' and game.item_required_level(item) != town.tier)
                or (town.rarity != 'All rarities' and item.rarity != town.rarity)
                or (town.affix != 'All affixes' and town.affix not in item.affix_stats)):
                continue
            result.append((kind,value,item))
        if town.sort == 'Price: Low to High':
            result.sort(key=lambda row:row[1]['price'] if row[0] == 'listing' else 0)
        elif town.sort == 'Price: High to Low':
            result.sort(key=lambda row:-(row[1]['price'] if row[0] == 'listing' else 0))
        elif town.sort == 'Tier: High to Low':
            result.sort(key=lambda row:-game.item_required_level(row[2]))
        return result

    def arm(operation,**payload):
        try:
            if operation in {'post','reprice'}:
                payload['price'] = parse_price(payload.pop('price_text',''))
                town.drafts['price'] = str(payload['price'])
            if operation == 'post':
                payload['expected'] = fingerprint(payload['item'])
            town.armed = {'operation':operation,**payload}
            town.notice,town.error = '',False
        except TownError as exc:
            town.notice,town.error = str(exc),True
        inspection.refresh()

    def commit():
        armed,town.armed = town.armed,None
        if not armed:
            return
        operation = armed.pop('operation')
        descriptions = {'post':'Local listing saved. The exact item is held in escrow, not published online.',
                        'reprice':'New price saved. No item was removed or duplicated.',
                        'cancel':'Listing returned to your pack. No fee charged.',
                        'buy':'Purchase saved. The item is in your pack and the seller was paid.'}
        _perform(town,actions,lambda:getattr(town,operation)(**armed),descriptions[operation])

    @ui.refreshable
    def listings():
        entries = rows()
        with ui.element('div').classes('nb-shelf').props(f'data-town-scroll="bazaar-{view}" aria-label="Bazaar items"'):
            if not entries:
                with ui.element('div').classes('nt-empty nb-empty'):
                    ui.icon('storefront',size='42px')
                    ui.label('A market needs adventurers.').classes('nt-section-display')
                    ui.label('There are no other same-mode local listings. Nothing here is generated stock or a simulated player. Marketplace still offers NPC equipment.').classes('pd-subtle')
                    ui.button('Visit Marketplace',on_click=lambda:actions['route']('marketplace')).classes('mq-btn-secondary')
                return
            if view == 'Ledger':
                for entry in entries:
                    with ui.element('article').classes('nb-ledger-row'):
                        ui.label(entry['kind']).classes('nb-ledger-kind')
                        ui.label(entry['name']).classes('nb-ledger-name')
                        ui.label(f'{entry["gold"]:+,}g' if entry['gold'] else 'NO GOLD MOVED').classes('nt-gold nb-ledger-gold')
                        ui.label(entry['other'] or 'Your local listing').classes('pd-subtle')
                        ui.label(date_label(entry['created'])).classes('pd-comparison-note')
                        if entry.get('item'):
                            item = game.Item.from_dict(entry['item'])
                            ui.html(inspect_item_html(item,game,key='town-ledger-'+entry['id'],caption='READ-ONLY RECORD'))
                return
            for kind,value,item in entries:
                key = str(id(value)) if kind == 'pack' else value['id']
                selected = town.selected is not None and town.selected[0] == kind and (town.selected[1] is value if kind == 'pack' else town.selected[1]['id'] == key)
                with ui.button(on_click=lambda k=kind,v=value:choose(k,v)).classes('nb-item'+(' selected' if selected else '')).style(item_visual_style(item,game)).props(f'aria-pressed={str(selected).lower()} aria-label="Inspect {text(item.name)} {key}" data-town-item="{key}"'):
                    price_html = f'<strong>{value["price"]:,}g</strong>' if kind == 'listing' else ''
                    ui.html(f'<img src="{text(game.item_icon_uri(item))}" alt="" draggable="false"><span><small>{"IN ESCROW" if kind == "listing" else "YOUR PACK"} / TIER {game.item_required_level(item)}</small><b>{text(item.name)}</b><em>{text(game.safe_item_short_stat_text(item))}</em></span>'+price_html)

    @ui.refreshable
    def inspection():
        town._draft_fields.pop('price',None)
        with ui.element('section').classes('nb-inspection'):
            eyebrow('YOUR SELECTION / CLICK TO PIN')
            if town.selected is None or view == 'Ledger':
                with ui.element('div').classes('nt-empty nb-selection-empty'):
                    ui.html('<div class="nb-scales" aria-hidden="true">I</div>')
                    ui.label('Know what changes hands.').classes('nt-section-display')
                    ui.label('Select an offer or a pack item. Full stats stay pinned here; hovering never replaces this decision.').classes('pd-subtle')
                return
            kind,value = town.selected
            item = value if kind == 'pack' else game.Item.from_dict(value['item'])
            with ui.element('div').classes('nb-item-sheet').style(item_visual_style(item,game)):
                ui.html(game.safe_rarity_badge_html(item))
                image_plate(game.item_icon_uri(item),item.name,'nb-selected-icon')
                ui.label(item.name).classes('nt-section-display')
                ui.label(f'Tier {game.item_required_level(item)} / {game.saved_item_type_label(item)}').classes('pd-subtle')
                ui.html(game.inventory_base_detail_html(item))
                ui.html(game.inventory_affix_detail_html(item))
            with ui.element('footer').classes('nb-decision'):
                if town.notice and town.error:
                    ui.label(town.notice).classes('nt-notice error').props('role=alert')
                if (kind == 'pack' or value['own']) and not town.armed:
                    price = ui.input('Price in gold',value=town.drafts.get('price','100')).props('dense outlined inputmode=numeric')
                    town._draft_fields['price'] = price
                    price.on_value_change(lambda e:town.drafts.__setitem__('price',str(e.value or '')) if town._draft_fields.get('price') is price else None)
                    ui.label('Local escrow only. Equipped, saved-set and companion items are not listed. No listing fee.').classes('pd-comparison-note')
                if town.armed:
                    a = town.armed
                    label = {'post':f'Hold this item in local escrow at {a.get("price",0):,}g?',
                             'reprice':f'Save a new asking price of {a.get("price",0):,}g?',
                             'cancel':'Return this exact item to your pack for free?',
                             'buy':f'Pay {a.get("expected_price",0):,}g for this exact offer?'}[a['operation']]
                    ui.label(label).classes('nt-confirm-copy')
                    with ui.element('div').classes('nt-inline-actions'):
                        ui.button('Not Yet',on_click=lambda:(setattr(town,'armed',None),inspection.refresh())).classes('mq-btn-secondary')
                        ui.button('Confirm '+{'post':'Listing','reprice':'Price','cancel':'Return','buy':'Purchase'}[a['operation']],on_click=commit).classes('mq-btn-gold')
                elif kind == 'pack':
                    ui.button('Review Local Listing',on_click=lambda:arm('post',item=value,price_text=price.value)).classes('mq-btn-gold')
                elif value['own']:
                    ui.label(f'{value["price"]:,}g asking price / Revision {value["revision"]}').classes('nt-gold')
                    with ui.element('div').classes('nt-inline-actions'):
                        ui.button('Change Price',on_click=lambda:arm('reprice',identity=value['id'],revision=value['revision'],price_text=price.value)).classes('mq-btn-gold')
                        ui.button('Return to Pack',on_click=lambda:arm('cancel',identity=value['id'],revision=value['revision'])).classes('mq-btn-secondary')
                else:
                    ui.label(f'{value["price"]:,}g / {value["seller"]}').classes('nt-gold')
                    buy = ui.button('Review Purchase',on_click=lambda:arm('buy',identity=value['id'],revision=value['revision'],expected_price=value['price'])).classes('mq-btn-gold')
                    buy.set_enabled(state.player.gold >= value['price'])

    with ui.element('main').classes('nt-workspace nb-workspace'):
        heading('THE BAZAAR / AN EXCHANGE BETWEEN ADVENTURERS','Every find has a future.','This profile only. Steam player trading is not connected.')
        receipt(town)
        with ui.element('nav').classes('nt-tabs').props('aria-label="Bazaar sections"'):
            for title in ['Browse','Sell & Manage','Ledger']:
                ui.button(title,on_click=lambda t=title:switch(t)).classes('mq-btn-secondary nt-tab'+(' selected' if view == title else '')).props('aria-pressed='+str(view == title).lower())
        with ui.element('div').classes('nb-layout'):
            with ui.element('section').classes('nb-library'):
                if view != 'Ledger':
                    with ui.element('div').classes('nb-filters'):
                        ui.input('Find an item',value=town.search,on_change=lambda e:changed('search',str(e.value or ''))).props('dense outlined clearable').classes('nb-search')
                        types = ['All types']+list(dict.fromkeys(game.saved_item_type_label(i) for i in state.player.inventory))+list(dict.fromkeys(game.saved_item_type_label(game.Item.from_dict(r['item'])) for r in town.listings()))
                        ui.select(list(dict.fromkeys(types)),label='Item type',value=town.kind if town.kind in types else 'All types',on_change=lambda e:changed('kind',e.value)).props('dense outlined')
                        ui.select({'All tiers':'All tiers',**{tier:f'Tier {tier}' for tier in game.ITEM_BUCKETS}},label='Tier',value=town.tier,on_change=lambda e:changed('tier',e.value)).props('dense outlined')
                        ui.select(['All rarities',*game.RARITY_COLORS],label='Rarity',value=town.rarity,on_change=lambda e:changed('rarity',e.value)).props('dense outlined')
                        ui.select({'All affixes':'All affixes',**{key:game.STAT_LABELS.get(key,key.replace('_',' ').title()) for key in game.CORE_STAT_KEYS+game.SECONDARY_AFFIX_KEYS}},label='Affix',value=town.affix,on_change=lambda e:changed('affix',e.value)).props('dense outlined')
                        ui.select(['Newest','Price: Low to High','Price: High to Low','Tier: High to Low'],label='Sort',value=town.sort,on_change=lambda e:changed('sort',e.value)).props('dense outlined')
                else:
                    eyebrow('YOUR LOCAL LEDGER / LATEST 200 ENTRIES')
                    ui.label('Real listings, returns and completed trades. Read-only item records are not extra inventory.').classes('pd-subtle')
                listings()
            inspection()


def render_guild(state,game,actions):
    town = town_for(state,game)
    town.enter('guild')
    guild = town.guild()

    def draft(key,label,placeholder=''):
        field = ui.input(label,value=town.drafts.get(key,''),placeholder=placeholder).props('dense outlined')
        town._draft_fields[key] = field
        field.on_value_change(lambda e:town.drafts.__setitem__(key,str(e.value or '')) if town._draft_fields.get(key) is field else None)
        return field

    def review_found(name,motto):
        town.drafts['guild-name'],town.drafts['guild-motto'] = str(name or ''),str(motto or '')
        town.armed = {'operation':'found','name':town.drafts.get('guild-name',''),'motto':town.drafts.get('guild-motto','')}
        actions['refresh']()

    def found():
        a,town.armed = town.armed,None
        if not a:
            town.notice,town.error = 'Your charter draft changed. Review it again.',True
            actions['refresh']()
            return
        _perform(town,actions,lambda:town.found(a['name'],a['motto']),'Charter sealed and saved. Your guild now belongs to this chronicle.')

    with ui.element('main').classes('nt-workspace ng-workspace'):
        heading('THE GUILD HALL / A NAME TO COME HOME TO','A light worth keeping.','Local charters and a private board. Steam guilds are not connected.')
        receipt(town)
        if not guild:
            with ui.element('div').classes('ng-founding-layout'):
                with ui.element('section').classes('ng-charter-art'):
                    ui.html('<div class="ng-crest" aria-hidden="true"><span>P</span><i></i></div>')
                    eyebrow('THE FIRST NAME ON THE ROLL')
                    ui.label('Begin with an oath.').classes('nt-display')
                    ui.label('A charter carries through your climbs. Gather your local chronicles under one name and keep a shared hall journal. No invented members or automated chat.').classes('pd-subtle')
                    ui.label('Local codes work only in this desktop profile. They do not invite Steam friends yet.').classes('nt-scope-note')
                with ui.element('section').classes('ng-charter-form'):
                    eyebrow('FOUND YOUR GUILD / 1,000 GOLD')
                    ui.label('Write the first page.').classes('nt-section-display')
                    reviewing = town.armed and town.armed.get('operation') == 'found'
                    if not reviewing:
                        name_field = draft('guild-name','Guild name','3-28 letters, numbers or simple punctuation')
                        motto_field = draft('guild-motto','Charter motto','What will your hall stand for?')
                    else:
                        town._draft_fields.pop('guild-name',None)
                        town._draft_fields.pop('guild-motto',None)
                        ui.label(town.armed['name']).classes('nt-section-display')
                        ui.label(town.armed['motto'] or 'Keep a light in the hall.').classes('ng-motto')
                    ui.label('The original main-game charter costs 1,000g, paid once on founding. Joining a local charter is free.').classes('pd-comparison-note')
                    if town.armed and town.armed.get('operation') == 'found':
                        ui.label(f'Seal "{town.armed["name"]}" for 1,000 gold?').classes('nt-confirm-copy')
                        ui.label('This creates a local charter, not a Steam guild.').classes('nt-scope-note')
                        with ui.element('div').classes('nt-inline-actions'):
                            ui.button('Revise Charter',on_click=lambda:(setattr(town,'armed',None),actions['refresh']())).classes('mq-btn-secondary')
                            ui.button('Seal Charter / 1,000g',on_click=found).classes('mq-btn-gold')
                    else:
                        create = ui.button('Review Charter',icon='verified',on_click=lambda:review_found(name_field.value,motto_field.value)).classes('mq-btn-gold')
                        create.set_enabled(state.player.gold >= 1000)
                    with ui.element('div').classes('ng-join'):
                        eyebrow('ALREADY INVITED?')
                        code = draft('guild-code','Local invitation code','G-...')
                        ui.button('Join Local Guild',on_click=lambda:_perform(town,actions,lambda:town.join(code.value),'You joined the local guild. Your items and gold are unchanged.')).classes('mq-btn-secondary')
            return
        with ui.element('div').classes('ng-hall-layout'):
            with ui.element('section').classes('ng-roster'):
                ui.html(f'<div class="ng-crest small" aria-hidden="true"><span>{text(guild["name"][:1].upper())}</span><i></i></div>')
                eyebrow('YOUR GUILD / CHARTERED '+date_label(guild['created']).split('/')[0].strip())
                ui.label(guild['name']).classes('nt-display')
                ui.label(guild.get('motto','') or 'Keep a light in the hall.').classes('ng-motto')
                ui.label('LOCAL INVITATION / THIS PROFILE ONLY').classes('pd-eyebrow')
                ui.label(guild['code']).classes('ng-code').props('tabindex=0')
                eyebrow(f'{len(guild["members"])} / {state.current_guild_member_limit()} MEMBERS')
                with ui.element('div').classes('ng-members').props('data-town-scroll="guild-roster"'):
                    for member in guild['members']:
                        raw = {'player_class':state.player.player_class,'level':state.player.level} if member['index'] == state.active_slot_index else member['player'] or {}
                        with ui.element('article').classes('ng-member'):
                            image_plate(game._hero_data_uri(raw.get('player_class','')) if raw else '',raw.get('player_class','Awaiting a new climb'),'ng-member-art')
                            with ui.element('div'):
                                ui.label(member['name']).classes('ng-member-name')
                                ui.label((raw.get('player_class','')+f' / Lv {raw.get("level",1)}') if raw else 'Between climbs').classes('pd-subtle')
                                ui.label(member['mode']+' / '+('FOUNDER' if member['founder'] else 'MEMBER')).classes('pd-comparison-note')
                with ui.element('footer').classes('ng-membership-actions'):
                    if town.armed and town.armed.get('operation') == 'leave':
                        ui.label('End this membership? A lone founder dissolves the local charter. The 1,000g charter fee is not refunded.').classes('nt-confirm-copy')
                        with ui.element('div').classes('nt-inline-actions'):
                            ui.button('Stay',on_click=lambda:(setattr(town,'armed',None),actions['refresh']())).classes('mq-btn-secondary')
                            ui.button('Confirm Leave',on_click=lambda:_perform(town,actions,town.leave,'Membership ended. Your items, gold and progression are unchanged.')).classes('mq-btn-danger')
                    else:
                        ui.button('Leave Guild',on_click=lambda:(setattr(town,'armed',{'operation':'leave'}),actions['refresh']())).classes('mq-btn-secondary')
            with ui.element('section').classes('ng-board'):
                with ui.element('header').classes('ng-board-heading'):
                    with ui.element('div'):
                        eyebrow('THE COMMON ROOM / PRIVATE GUILD BOARD')
                        ui.label('Leave a light for the next visit.').classes('nt-section-display')
                    ui.label('No background polling.').classes('pd-comparison-note')
                with ui.element('div').classes('ng-messages').props('data-town-scroll="guild-board" aria-label="Guild board messages"'):
                    if not guild['messages']:
                        with ui.element('div').classes('nt-empty'):
                            ui.icon('forum',size='38px')
                            ui.label('The first page is yours.').classes('nt-section-display')
                            ui.label('Leave a build idea, an expedition goal or a word for your other chronicles. Messages stay with this local charter.').classes('pd-subtle')
                    for message in reversed(guild['messages']):
                        with ui.element('article').classes('ng-message'):
                            ui.label(message['author']).classes('ng-member-name')
                            ui.label(date_label(message['created'])).classes('pd-comparison-note')
                            ui.label(message['body']).classes('ng-message-body')
                with ui.element('footer').classes('ng-composer'):
                    body = draft('guild-body','Message to your guild','Up to 220 characters. No auto-refresh while you type.')
                    def send():
                        try:
                            town.message(body.value)
                            town.drafts['guild-body'] = ''
                            body.set_value('')
                            town.notice,town.error = 'Message saved to the local guild board.',False
                        except (TownError,DesktopTransactionError) as exc:
                            town.notice,town.error = str(exc),True
                        actions['refresh']()
                    body.on('keydown.enter',lambda:send())
                    ui.button('Post to Board',icon='send',on_click=send).classes('mq-btn-gold')


def render_ladder(state,game,actions):
    town = town_for(state,game)
    town.enter('ladder')
    mode = town.drafts.get('ladder-mode',state.current_slot_mode())
    order = town.drafts.get('ladder-sort','Highest Level')
    tab = town.drafts.get('ladder-tab','Standings')
    selected_class = town.drafts.get('ladder-class','All classes')
    def changed(key,value):
        town.drafts[key] = value
        if key=='ladder-class' and value!='All classes':
            town.drafts['ladder-sort'] = 'Fastest Ascent'
        actions['refresh']()
    def switch(value):
        town.drafts['ladder-tab'] = value
        actions['refresh']()

    @ui.refreshable
    def board():
        rows = [row for row in town.ladder(None if selected_class=='All classes' else selected_class) if town.drafts.get('ladder-mode',mode) in {'All Local Chronicles',row['mode']}]
        sort = town.drafts.get('ladder-sort',order)
        if sort == 'Victories':
            rows.sort(key=lambda row:(-row['wins'],-row['level'],row['index']))
        elif sort == 'Fastest Ascent':
            rows.sort(key=lambda row:(row['fastest'] is None,row['fastest'] or 0,row['index']))
        with ui.element('div').classes('nl-table').props('data-town-scroll="ladder" aria-label="Local chronicle standings"'):
            if not rows:
                with ui.element('div').classes('nt-empty'):
                    ui.label('A page waiting for a legend.').classes('nt-section-display')
                    ui.label('Only actual saved chronicles appear. No sample opponents or invented ranks.').classes('pd-subtle')
            for rank,row in enumerate(rows,1):
                with ui.element('article').classes('nl-row'+(' yours' if row['current'] else '')):
                    ui.label(f'{rank:02}').classes('nl-rank')
                    image_plate(game._hero_data_uri(row['class']),row['class'],'nl-portrait')
                    with ui.element('div').classes('nl-identity'):
                        ui.label(row['name']).classes('nl-name')
                        ui.label(row['class'] if row['active'] or selected_class!='All classes' else 'Between climbs').classes('pd-subtle')
                        if selected_class!='All classes' and row['pq_name'] and row['pq_name']!=row['name']:
                            ui.label('PQ by '+row['pq_name']).classes('pd-comparison-note')
                        ui.label(row['mode']+(' / YOU' if row['current'] else '')).classes('pd-comparison-note')
                    with ui.element('div').classes('nl-value'):
                        ui.label(str(row['level']) if row['active'] else '--')
                        ui.label('LEVEL').classes('pd-comparison-note')
                    with ui.element('div').classes('nl-value'):
                        ui.label(f'{row["wins"]:,}')
                        ui.label('VICTORIES').classes('pd-comparison-note')
                    with ui.element('div').classes('nl-value'):
                        ui.label(f'{int(row["fastest"]//60)}m {int(row["fastest"]%60):02}s' if row['fastest'] else '--')
                        ui.label('FASTEST PQ').classes('pd-comparison-note')

    with ui.element('main').classes('nt-workspace nl-workspace'):
        heading('THE REALM LADDER / THE CLIMB, RECORDED','Let the climb speak.','Actual local chronicles only. This is not a Steam or global leaderboard.')
        with ui.element('nav').classes('nt-tabs').props('aria-label="Ladder sections"'):
            for title in ['Standings','My Ascents']:
                ui.button(title,on_click=lambda t=title:switch(t)).classes('mq-btn-secondary nt-tab'+(' selected' if title == tab else '')).props('aria-pressed='+str(title == tab).lower())
            ui.select(['All classes',*game.ALL_CLASS_ORDER],label='Class',value=selected_class,on_change=lambda e:changed('ladder-class',e.value)).classes('nl-class-filter').props('outlined dense')
        with ui.element('div').classes('nl-layout'):
            with ui.element('aside').classes('nl-your-climb'):
                with ui.element('div').classes('nl-your-summary'):
                    eyebrow('YOUR CURRENT CHRONICLE')
                    image_plate(game._hero_data_uri(state.player.player_class),state.player.player_class,'nl-your-art')
                    ui.label(state.player.name).classes('nt-section-display')
                    ui.label(state.player.player_class).classes('pd-subtle')
                    ui.html(f'<div class="nl-level"><b>{state.player.level}</b><span>LEVEL</span></div>')
                    ui.label(f'{state.player.wins:,} victories / {state.player.losses:,} defeats').classes('pd-subtle')
                    attempts = state.slots[state.active_slot_index].get('pq_ledger_entries',[])
                    ui.label(f'{sum(bool(row.get("passed")) for row in attempts)} successful ascents / {len(attempts)} attempts').classes('pd-comparison-note')
                    ui.label('No seasonal wipe, data upload or character replacement is performed by this screen.').classes('nt-scope-note')
                ui.button('Continue the Climb',icon='arrow_forward',on_click=lambda:actions['route']('arena')).classes('mq-btn-gold')
            with ui.element('section').classes('nl-records'):
                if tab == 'Standings':
                    with ui.element('div').classes('nl-filters'):
                        ui.select([state.current_slot_mode(),*filter(lambda x:x != state.current_slot_mode(),['Core','SSF','HC']),'All Local Chronicles'],label='Chronicle mode',value=mode,on_change=lambda e:changed('ladder-mode',e.value)).props('dense outlined')
                        ui.select(['Highest Level','Victories','Fastest Ascent'],label='Rank by',value=order,on_change=lambda e:changed('ladder-sort',e.value)).props('dense outlined')
                    ui.label('Class filters rank successful PQ times for that class. Level and victories remain your current chronicle stats. Modes stay separate unless you choose All Local Chronicles.').classes('pd-comparison-note')
                    board()
                else:
                    eyebrow('YOUR PRISMATIC QUEST RECORD / THIS CHRONICLE')
                    with ui.element('div').classes('nl-history').props('data-town-scroll="pq-history"'):
                        if not attempts:
                            with ui.element('div').classes('nt-empty'):
                                ui.label('Your first ascension is ahead.').classes('nt-section-display')
                                ui.label('Reach level 60 and approach the Prism. Every real attempt will be recorded here.').classes('pd-subtle')
                        matching_attempts = [entry for entry in reversed(attempts) if selected_class=='All classes' or entry.get('player_class')==selected_class]
                        if attempts and not matching_attempts:
                            ui.label('No recorded ascents for this class yet.').classes('pd-subtle')
                        for entry in matching_attempts:
                            with ui.element('article').classes('nl-ascent '+('passed' if entry.get('passed') else 'failed')):
                                ui.label('ASCENDED' if entry.get('passed') else 'THE PRISM REFUSED').classes('pd-eyebrow')
                                ui.label(entry.get('player_class','Adventurer')).classes('nt-section-title')
                                ui.label(entry.get('character_name','Your hero')).classes('pd-subtle')
                                seconds = float(entry.get('elapsed_seconds',0))
                                ui.label(f'{int(seconds//60)}m {int(seconds%60):02}s / '+date_label(entry.get('completed_at',''))).classes('pd-comparison-note')
