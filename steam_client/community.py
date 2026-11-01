"""Current-chronicle town services. Local records never enter a trusted online realm.

Escrow, payment and both sides of a local trade share the existing atomic save.
No second character, test kit, fabricated buyer, background poll or cloud upload.
"""

import copy
import re
import uuid
from datetime import UTC, datetime

from .chapters import atomic_progress, fingerprint, hero_key
from .town_data import empty_town, normalize_town


class TownError(ValueError):
    pass


def stamp():
    return datetime.now(UTC).isoformat(timespec='seconds')


def price_value(value):
    if type(value) is not int or not 1 <= value <= 1_000_000:
        raise TownError('Use a whole-number price from 1 to 1,000,000 gold.')
    return value


def parse_price(value):
    raw = str(value or '').strip()
    if not re.fullmatch(r'(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)',raw):
        raise TownError('Enter a whole-number gold price, such as 125 or 1,000.')
    return price_value(int(raw.replace(',','')))


class Town:
    def __init__(self,state,game):
        self.state,self.game,self.owner = state,game,hero_key(state)
        self.view,self.selected,self.armed = 'Browse',None,None
        self.search,self.kind,self.tier,self.rarity,self.affix,self.sort = '','All types','All tiers','All rarities','All affixes','Newest'
        self.drafts = {}
        self._draft_fields = {}
        self.notice,self.error,self.receipt = '',False,None
        self.scene = None

    def enter(self,scene):
        if self.scene != scene:
            self.scene = scene
            self.notice,self.error,self.receipt = '',False,None
            self.selected,self.armed = None,None
            self._draft_fields.clear()

    @property
    def index(self):
        return self.state.active_slot_index

    def data(self,index=None):
        return normalize_town(self.state.slots[self.index if index is None else index].get('town_services',{}))

    def _edit(self,index=None):
        slot = self.state.slots[self.index if index is None else index]
        if not isinstance(slot.get('town_services'),dict) or any(key not in slot['town_services'] for key in empty_town()):
            slot['town_services'] = self.data(index)
        return slot['town_services']

    def _name(self,index=None):
        index = self.index if index is None else index
        if index == self.index and self.state.player is not None:
            return self.state.player.name
        slot = self.state.slots[index]
        return (slot.get('player') or {}).get('name') or self.data(index)['last_name'] or self.game.slot_title_for_index(index)+' Chronicle'

    def _guard(self,trade=False):
        if self.owner != hero_key(self.state) or self.state.player is None:
            raise TownError('Your hero changed. Reopen this destination.')
        if self.state.fight_in_progress or self.state.current_monster is not None:
            raise TownError('Finish the encounter before managing town business.')
        if trade and self.state.current_slot_mode() == 'SSF':
            raise TownError('The Bazaar is sealed in SSF. This chronicle remains self-found.')

    def _commit(self,action):
        def save():
            result = action()
            self._edit()['last_name'] = self.state.player.name
            self.state.sync_active_slot()
            return result
        result = atomic_progress(self.state,save,failure_message='This town action could not be saved. Previous items, gold and town records were restored. Check storage and retry.')
        self.armed = None
        return result

    def _record(self,index,kind,gold,item=None,other=''):
        data = self._edit(index)
        data['ledger'].insert(0,{'id':uuid.uuid4().hex,'kind':kind,'gold':gold,'other':other,'created':stamp(),
                                'name':item['name'] if item else '', 'item':copy.deepcopy(item)})
        data['ledger'] = data['ledger'][:200]
        inactive = [row for row in data['listings'] if row['status'] != 'active'][-100:]
        keep = {row['id'] for row in inactive}
        data['listings'] = [row for row in data['listings'] if row['status'] == 'active' or row['id'] in keep]

    def _invalidate_pack_selection(self):
        self.state.selected_inventory_key = ''
        self.state.hovered_inventory_key = ''
        self.state.inn_vault_inventory_selected_index = -1

    def listings(self):
        rows = []
        mode = self.state.current_slot_mode()
        if mode == 'SSF':
            return rows
        for index in range(len(self.state.slots)):
            if self.game.slot_mode_for_index(index) != mode:
                continue
            for listing in self.data(index)['listings']:
                if listing['status'] == 'active':
                    rows.append({**listing,'seller_index':index,'seller':self._name(index),'own':index == self.index})
        return sorted(rows,key=lambda row:(row['created'],row['id']),reverse=True)

    def _listing(self,identity,revision,*,own=True):
        row = next((row for row in self.listings() if row['id'] == identity),None)
        if row is None or row['revision'] != revision:
            raise TownError('The listing changed or is no longer active. Select its current version.')
        if own != row['own']:
            raise TownError('You cannot buy your own listing.' if not own else 'Only the seller can change this listing.')
        data = self._edit(row['seller_index'])
        actual = next(candidate for candidate in data['listings'] if candidate['id'] == identity)
        return row,actual

    def post(self,item,price,expected=None):
        self._guard(trade=True)
        price_value(price)
        if not any(candidate is item for candidate in self.state.player.inventory):
            raise TownError('That exact item is no longer in your pack. Choose it again.')
        if expected is not None and fingerprint(item) != expected:
            raise TownError('The item changed. Inspect and review its current details.')
        if sum(row['own'] for row in self.listings()) >= 100:
            raise TownError('You already have 100 active listings. Return one before posting another.')
        def apply():
            index = next(i for i,candidate in enumerate(self.state.player.inventory) if candidate is item)
            payload = self.state.player.inventory.pop(index).to_dict()
            self._invalidate_pack_selection()
            row = {'id':uuid.uuid4().hex,'item':payload,'price':price,'revision':1,'status':'active','created':stamp(),'updated':stamp()}
            self._edit()['listings'].append(row)
            self._record(self.index,'Listed locally',0,payload)
            return copy.deepcopy(row)
        return self._commit(apply)

    def reprice(self,identity,revision,price):
        self._guard(trade=True)
        price_value(price)
        # Validate without editing; a stale review must not initialize anything.
        row = next((r for r in self.listings() if r['id'] == identity and r['own']),None)
        if row is None or row['revision'] != revision:
            raise TownError('The listing changed. Select its current price again.')
        def apply():
            _,actual = self._listing(identity,revision)
            actual['price'],actual['revision'],actual['updated'] = price,revision+1,stamp()
            self._record(self.index,'Price changed',0,actual['item'])
            return copy.deepcopy(actual)
        return self._commit(apply)

    def cancel(self,identity,revision):
        self._guard(trade=True)
        row = next((r for r in self.listings() if r['id'] == identity and r['own']),None)
        if row is None or row['revision'] != revision:
            raise TownError('The listing changed or was already returned.')
        def apply():
            _,actual = self._listing(identity,revision)
            item = self.game.Item.from_dict(actual['item'])
            self.state.player.inventory.append(item)
            self._invalidate_pack_selection()
            actual['status'],actual['revision'],actual['updated'] = 'returned',revision+1,stamp()
            self._record(self.index,'Returned to pack',0,actual['item'])
            return item
        return self._commit(apply)

    def buy(self,identity,revision,expected_price):
        self._guard(trade=True)
        row = next((r for r in self.listings() if r['id'] == identity),None)
        if row is None or row['own'] or row['revision'] != revision or row['price'] != expected_price:
            raise TownError('The offer changed or belongs to you. Review its current price.')
        if self.state.player.gold < expected_price:
            raise TownError('You do not have enough gold for this offer.')
        seller = row['seller_index']
        if self.state.slots[seller].get('season_id',1) != self.state.slots[self.index].get('season_id',1):
            raise TownError('This offer belongs to a different season.')
        def apply():
            _,actual = self._listing(identity,revision,own=False)
            self.state.player.gold -= expected_price
            seller_slot = self.state.slots[seller]
            if seller_slot.get('player'):
                seller_slot['player']['gold'] += expected_price
            else:
                seller_slot['carryover_gold'] = int(seller_slot.get('carryover_gold',0))+expected_price
            item = self.game.Item.from_dict(actual['item'])
            self.state.player.inventory.append(item)
            self._invalidate_pack_selection()
            actual['status'],actual['revision'],actual['updated'] = 'sold',revision+1,stamp()
            self._record(self.index,'Bought',-expected_price,actual['item'],self._name(seller))
            self._record(seller,'Sold',expected_price,actual['item'],self._name())
            return item
        return self._commit(apply)

    def guild(self):
        identity = self.data()['guild_id']
        if not identity:
            return None
        for index in range(len(self.state.slots)):
            charter = next((row for row in self.data(index)['charters'] if row['id'] == identity),None)
            if charter:
                members = [{'index':i,'name':self._name(i),'founder':i == charter['founder'],
                            'mode':self.game.slot_mode_for_index(i),'player':self.state.slots[i].get('player')}
                           for i in range(len(self.state.slots)) if self.data(i)['guild_id'] == identity]
                return {**charter,'members':members,'owner_index':index}
        return None

    def found(self,name,motto=''):
        self._guard()
        name,motto = ' '.join(str(name).split()),' '.join(str(motto).split())
        if not 3 <= len(name) <= 28 or not re.fullmatch(r"[A-Za-z0-9 _'.-]+",name):
            raise TownError('Use a guild name of 3-28 letters, numbers, spaces or simple punctuation.')
        if len(motto)>100:
            raise TownError('Keep the charter motto to 100 characters.')
        if self.data()['guild_id']:
            raise TownError('You already belong to a guild. Leave it before founding another.')
        if any(row['name'].casefold() == name.casefold() for i in range(len(self.state.slots)) for row in self.data(i)['charters']):
            raise TownError('That local guild name is already in use.')
        if self.state.player.gold < 1000:
            raise TownError('A main-game guild charter costs 1,000 gold.')
        def apply():
            row = {'id':uuid.uuid4().hex,'code':'G-'+uuid.uuid4().hex[:10].upper(),'name':name,'motto':motto,'founder':self.index,'created':stamp(),'messages':[]}
            data = self._edit()
            data['charters'].append(row)
            data['guild_id'] = row['id']
            self.state.player.gold -= 1000
            self.state.record_town_service_spend('guild_charter',1000)
            return copy.deepcopy(row)
        return self._commit(apply)

    def join(self,code):
        self._guard()
        if self.data()['guild_id']:
            raise TownError('Leave your current guild before joining another.')
        code = str(code).strip().upper()
        found = next((row for i in range(len(self.state.slots)) for row in self.data(i)['charters'] if row['code'] == code),None)
        if not found:
            raise TownError('No local charter matches that code. Codes here work only within this desktop profile.')
        members = sum(self.data(i)['guild_id'] == found['id'] for i in range(len(self.state.slots)))
        if members >= self.state.current_guild_member_limit():
            raise TownError('This guild has reached its member limit.')
        return self._commit(lambda:self._edit().__setitem__('guild_id',found['id']))

    def leave(self):
        self._guard()
        guild = self.guild()
        if not guild:
            raise TownError('You are not a member of a local guild.')
        if guild['founder'] == self.index and len(guild['members']) > 1:
            raise TownError('The founder cannot leave while other members remain.')
        def apply():
            self._edit()['guild_id'] = ''
            if guild['founder'] == self.index:
                data = self._edit(guild['owner_index'])
                data['charters'] = [row for row in data['charters'] if row['id'] != guild['id']]
        return self._commit(apply)

    def message(self,body):
        self._guard()
        body = str(body).strip()
        if not 1 <= len(body) <= 220 or any(ord(char)<32 for char in body):
            raise TownError('Messages must be 1-220 characters without control characters.')
        guild = self.guild()
        if not guild:
            raise TownError('Join a guild before writing on its board.')
        def apply():
            charter = next(row for row in self._edit(guild['owner_index'])['charters'] if row['id'] == guild['id'])
            charter['messages'].insert(0,{'id':uuid.uuid4().hex,'author':self._name(),'body':body,'created':stamp()})
            charter['messages'] = charter['messages'][:80]
        return self._commit(apply)

    def ladder(self):
        rows = []
        for index,slot in enumerate(self.state.slots):
            player = self.state.player if index == self.index else None
            raw = slot.get('player') or {}
            entries = slot.get('pq_ledger_entries',[])
            if not raw and not player and not entries:
                continue
            successful = [float(row['elapsed_seconds']) for row in entries if row.get('passed') and row.get('elapsed_seconds',0)>0]
            current_class = player.player_class if player else raw.get('player_class') or self.game.slot_highest_class(slot) or ''
            rows.append({'index':index,'name':self._name(index),'class':current_class,'level':player.level if player else int(raw.get('level',0)),
                         'wins':player.wins if player else int(raw.get('wins',0)), 'losses':player.losses if player else int(raw.get('losses',0)),
                         'mode':self.game.slot_mode_for_index(index),'fastest':min(successful) if successful else None,'attempts':len(entries),
                         'ascensions':sum(bool(row.get('passed')) for row in entries),'current':index == self.index,'active':bool(player or raw)})
        return sorted(rows,key=lambda row:(-row['level'],-row['wins'],row['name'].casefold(),row['index']))


def town_for(state,game):
    current = getattr(state,'_desktop_town',None)
    if current is None or current.owner != hero_key(state):
        state._desktop_town = Town(state,game)
    return state._desktop_town
