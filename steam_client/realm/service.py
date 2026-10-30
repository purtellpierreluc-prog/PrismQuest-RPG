"""Transactional realm authority shared by the preview and hosted HTTP service.

Only this service creates progression, currency and items. Commands contain IDs,
never client-authored item stats or character snapshots.
"""

import copy
import hashlib
import json
import re
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from pathlib import Path


class RealmError(ValueError):
    pass


def encode(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'))


def label(value, maximum=28):
    value = str(value).strip()
    if not 2 <= len(value) <= maximum or not re.fullmatch(r"[A-Za-z0-9 _'.-]+", value):
        raise RealmError(f'Use 2-{maximum} letters, numbers, spaces or simple punctuation.')
    return value


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise RealmError(f'Enter a whole number from {low:,} to {high:,}.')
    return value


class Realm:
    def __init__(self, path, rules, *, sandbox=True, clock=time.time):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.rules, self.sandbox, self.clock = rules, sandbox, clock
        self.lock = threading.RLock()
        self.rates = defaultdict(deque)
        with self.connection() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS meta (id INTEGER PRIMARY KEY, revision INTEGER NOT NULL);
                INSERT OR IGNORE INTO meta VALUES (1,0);
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, identity TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
                    code TEXT UNIQUE NOT NULL, player TEXT NOT NULL, kit INTEGER NOT NULL DEFAULT 0,
                    level INTEGER NOT NULL DEFAULT 1, wins INTEGER NOT NULL DEFAULT 0, class TEXT NOT NULL DEFAULT 'Black Guard');
                CREATE INDEX IF NOT EXISTS ladder_rank ON users(level DESC,wins DESC,name);
                CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS items (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, location TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS items_owner ON items(owner, location);
                CREATE UNIQUE INDEX IF NOT EXISTS single_equipment ON items(owner,location) WHERE location LIKE 'equip:%';
                CREATE TABLE IF NOT EXISTS listings (
                    id TEXT PRIMARY KEY, seller TEXT NOT NULL, item_id TEXT UNIQUE NOT NULL,
                    price INTEGER NOT NULL CHECK(price > 0), active INTEGER NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS deliveries (
                    id TEXT PRIMARY KEY, sender TEXT NOT NULL, recipient TEXT NOT NULL,
                    item_id TEXT UNIQUE NOT NULL, claimed INTEGER NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS ledger (
                    id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, other TEXT NOT NULL,
                    kind TEXT NOT NULL, gold INTEGER NOT NULL, item TEXT NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS requests (
                    user_id TEXT NOT NULL, key TEXT NOT NULL, digest TEXT NOT NULL, result TEXT NOT NULL,
                    PRIMARY KEY(user_id,key));
                CREATE TABLE IF NOT EXISTS parties (id TEXT PRIMARY KEY, code TEXT UNIQUE NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS party_members (user_id TEXT PRIMARY KEY, party_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS guilds (id TEXT PRIMARY KEY, code TEXT UNIQUE NOT NULL, leader TEXT NOT NULL, name TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS guild_members (user_id TEXT PRIMARY KEY, guild_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, channel TEXT NOT NULL,
                    body TEXT NOT NULL, created REAL NOT NULL);
            ''')

    @contextmanager
    def connection(self):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA busy_timeout=5000')
            try:
                yield db
            finally:
                db.close()

    def _limit(self, user, bucket, count=40, seconds=60):
        key = (user, bucket)
        now = self.clock()
        queue = self.rates[key]
        while queue and queue[0] <= now - seconds:
            queue.popleft()
        if len(queue) >= count:
            raise RealmError('Please wait a moment before trying again.')
        queue.append(now)
        if len(self.rates) > 5000:
            for old in [k for k, values in self.rates.items() if not values or values[-1] < now - 300]:
                self.rates.pop(old, None)

    def login(self, identity, name, player_class='Black Guard'):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                row = db.execute('SELECT id FROM users WHERE identity=?', (identity,)).fetchone()
                if row:
                    uid = row['id']
                else:
                    name = label(name)
                    player = self.rules.create(name, player_class)
                    uid = secrets.token_hex(16)
                    db.execute('INSERT INTO users(id,identity,name,code,player) VALUES (?,?,?,?,?)',
                               (uid, identity, name, 'PQ-' + secrets.token_hex(8).upper(), '{}'))
                    self._save_player(db, uid, player)
                    db.execute('UPDATE meta SET revision=revision+1 WHERE id=1')
                token = secrets.token_urlsafe(48)
                db.execute('DELETE FROM sessions WHERE expires<?', (self.clock(),))
                db.execute('INSERT INTO sessions VALUES (?,?,?)', (self._digest(token), uid, self.clock() + 86400))
                db.execute('COMMIT')
                return token
            except BaseException:
                db.execute('ROLLBACK')
                raise

    @staticmethod
    def _digest(value):
        return hashlib.sha256(value.encode('utf-8')).hexdigest()

    def _user(self, db, token):
        row = db.execute('SELECT user_id FROM sessions WHERE token=? AND expires>?',
                         (self._digest(token), self.clock())).fetchone()
        if not row:
            raise RealmError('Your realm session expired. Reconnect; your realm progress is preserved.')
        return row['user_id']

    def logout(self, token):
        with self.connection() as db:
            db.execute('DELETE FROM sessions WHERE token=?', (self._digest(token),))

    def _player(self, db, uid):
        raw = json.loads(db.execute('SELECT player FROM users WHERE id=?', (uid,)).fetchone()[0])
        raw['inventory'] = []
        raw['equipped'] = {'weapon': None, 'armor': None, 'charm': None}
        for row in db.execute('SELECT location,payload FROM items WHERE owner=? ORDER BY id', (uid,)):
            if row['location'] == 'pack':
                raw['inventory'].append(json.loads(row['payload']))
            elif row['location'].startswith('equip:'):
                raw['equipped'][row['location'].split(':')[1]] = json.loads(row['payload'])
        return self.rules.game.Player.from_dict(raw)

    def _save_player(self, db, uid, player):
        raw = player.to_dict()
        desired = [('pack', item) for item in raw.pop('inventory', [])]
        desired += [('equip:' + slot, item) for slot, item in raw.pop('equipped', {}).items() if item]
        existing = list(db.execute("SELECT * FROM items WHERE owner=? AND (location='pack' OR location LIKE 'equip:%')", (uid,)))
        for location, payload in desired:
            encoded = encode(payload)
            match = next((row for row in existing if row['location'] == location and row['payload'] == encoded), None)
            if match:
                existing.remove(match)
            else:
                db.execute('INSERT INTO items VALUES (?,?,?,?)', (secrets.token_hex(16), uid, location, encoded))
        if existing:
            raise RealmError('Item conservation check failed. Nothing was changed.')
        db.execute('UPDATE users SET player=?,level=?,wins=?,class=? WHERE id=?', (encode(raw), player.level, player.wins, player.player_class, uid))

    def _idle(self, db, uid):
        party = self._party(db, uid)
        if party and party['checkpoint']:
            raise RealmError('Finish or leave the shared expedition before changing gear, trading or training.')

    def _party(self, db, uid):
        row = db.execute('SELECT p.id,p.code,p.data FROM parties p JOIN party_members m ON m.party_id=p.id WHERE m.user_id=?', (uid,)).fetchone()
        return dict(json.loads(row['data']), id=row['id'], code=row['code']) if row else None

    def _store_party(self, db, party):
        db.execute('UPDATE parties SET data=? WHERE id=?', (encode(party), party['id']))

    def _owned(self, db, uid, item_id, locations):
        row = db.execute('SELECT * FROM items WHERE id=? AND owner=?', (str(item_id), uid)).fetchone()
        if not row or row['location'] not in locations:
            raise RealmError('That item is no longer available in the selected location. Refresh and select it again.')
        return row

    def _record(self, db, uid, other, kind, gold, item):
        db.execute('INSERT INTO ledger(user_id,other,kind,gold,item,created) VALUES (?,?,?,?,?,?)',
                   (uid, other, kind, gold, item, self.clock()))

    def command(self, token, key, operation, args=None):
        args = args or {}
        if not isinstance(operation, str) or not re.fullmatch(r'[a-z_]{2,32}', operation) or not isinstance(args, dict) or len(encode(args)) > 4096 or not re.fullmatch(r'[A-Za-z0-9_-]{16,80}', str(key)):
            raise RealmError('Invalid command envelope.')
        digest = self._digest(encode([operation, args]))
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                uid = self._user(db, token)
                prior = db.execute('SELECT digest,result FROM requests WHERE user_id=? AND key=?', (uid, key)).fetchone()
                if prior:
                    if prior['digest'] != digest:
                        raise RealmError('A request key was reused for a different action.')
                    db.execute('COMMIT')
                    return json.loads(prior['result'])
                self._limit(uid, 'commands', 90)
                try:
                    message = self._dispatch(db, uid, operation, args)
                except ValueError as exc:
                    raise RealmError(str(exc)) from None
                db.execute('UPDATE meta SET revision=revision+1 WHERE id=1')
                result = {'message': message, 'revision': db.execute('SELECT revision FROM meta').fetchone()[0]}
                db.execute('INSERT INTO requests VALUES (?,?,?,?)', (uid, key, digest, encode(result)))
                db.execute('COMMIT')
                return result
            except BaseException:
                db.execute('ROLLBACK')
                raise

    def _dispatch(self, db, uid, op, args):
        g = self.rules.game
        if op in {'arena', 'recover', 'allocate', 'equip', 'list', 'buy', 'cancel', 'reprice', 'send', 'claim', 'deposit', 'withdraw', 'test_kit'}:
            self._idle(db, uid)
        if op == 'test_kit':
            if not self.sandbox or db.execute('SELECT kit FROM users WHERE id=?', (uid,)).fetchone()[0]:
                raise RealmError('Test kits are available once per character, only in the local/sandbox realm.')
            p = self._player(db, uid)
            while p.level < 45:
                while p.unspent_stat_points > 0:
                    p.allocate_core_stat('vitality' if p.unspent_stat_points % 4 == 0 else 'intelligence' if p.player_class in ('Shadow Mage', 'Night Angel') else 'strength')
                g.gain_xp(p, p.xp_to_next - p.xp, None)
            for _point in range(p.unspent_stat_points // 4):
                p.allocate_core_stat('vitality')
            while p.unspent_stat_points > 0:
                p.allocate_core_stat('intelligence' if p.player_class in ('Shadow Mage', 'Night Angel') else 'strength')
            p.gold += 2000
            for slot, old in list(p.equipped.items()):
                if old:
                    db.execute("UPDATE items SET location='pack' WHERE owner=? AND location=?", (uid, 'equip:' + slot))
                    p.inventory.append(old)
                    p.equipped[slot] = g.generate_specific_item(45, slot, old.subtype, 'Common')
            p.recalculate_stats()
            p.hp, p.mana = p.max_hp, p.max_mana
            p.inventory += [g.generate_item_drop(45, p.player_class, 0) for _ in range(4)]
            self._save_player(db, uid, p)
            db.execute('UPDATE users SET kit=1 WHERE id=?', (uid,))
            return 'Test character prepared: level 45, common tier-45 gear, 2,000 gold and four test finds. Solo saves were not touched.'
        if op == 'arena':
            p = self._player(db, uid)
            result = self.rules.arena(p)
            self._save_player(db, uid, p)
            self._record(db, uid, '', 'Arena victory' if result['gold'] else 'Arena defeat', result['gold'], result['monster'].get('monster_type', 'Monster'))
            return result['log'][-1] + (f" +{result['gold']} gold." if result['gold'] else '')
        if op in {'recover', 'allocate'}:
            p = self._player(db, uid)
            if op == 'recover':
                p.hp, p.mana = p.max_hp, p.max_mana
                message = 'Recovered at the realm Inn.'
            else:
                stat = args.get('stat')
                if stat not in ('strength', 'dexterity', 'intelligence', 'vitality') or p.unspent_stat_points < 1:
                    raise RealmError('No point is available for that stat.')
                message = p.allocate_core_stat(stat)
            self._save_player(db, uid, p)
            return message
        if op in {'deposit', 'withdraw', 'equip', 'list', 'send'}:
            locations = {'deposit': ['pack'], 'withdraw': ['vault'], 'equip': ['pack'], 'list': ['pack', 'vault'], 'send': ['pack', 'vault']}[op]
            item = self._owned(db, uid, args.get('item'), locations)
            payload = json.loads(item['payload'])
            if op == 'equip':
                p = self._player(db, uid)
                allowed, reason = g.can_player_equip_item(p, g.Item.from_dict(payload))
                if not allowed:
                    raise RealmError(reason)
                location = 'equip:' + payload['slot']
                db.execute("UPDATE items SET location='pack' WHERE owner=? AND location=?", (uid, location))
                db.execute('UPDATE items SET location=? WHERE id=?', (location, item['id']))
                p = self._player(db, uid)
                p.recalculate_stats()
                self._save_player(db, uid, p)
            elif op in ('deposit', 'withdraw'):
                db.execute('UPDATE items SET location=? WHERE id=?', ('vault' if op == 'deposit' else 'pack', item['id']))
            elif op == 'list':
                price = integer(args.get('price'), 1, 1_000_000)
                db.execute("UPDATE items SET location='listing' WHERE id=?", (item['id'],))
                db.execute('INSERT INTO listings VALUES (?,?,?,?,1,?)', (secrets.token_hex(16), uid, item['id'], price, self.clock()))
            else:
                recipient = db.execute('SELECT id,name FROM users WHERE code=?', (str(args.get('code', '')).strip().upper(),)).fetchone()
                if not recipient or recipient['id'] == uid:
                    raise RealmError('Enter another realm player\'s exact vault code.')
                db.execute("UPDATE items SET owner=?,location='courier' WHERE id=?", (recipient['id'], item['id']))
                db.execute('INSERT INTO deliveries VALUES (?,?,?,?,0,?)',
                           (secrets.token_hex(16), uid, recipient['id'], item['id'], self.clock()))
                self._record(db, uid, recipient['name'], 'Sent', 0, payload['name'])
                self._record(db, recipient['id'], self._name(db, uid), 'Incoming', 0, payload['name'])
            return {'deposit': 'Item deposited.', 'withdraw': 'Item withdrawn.', 'equip': 'Equipment updated.', 'list': 'Listing created.', 'send': 'Item sent safely to the recipient\'s courier inbox.'}[op]
        if op == 'claim':
            row = db.execute('SELECT * FROM deliveries WHERE id=? AND recipient=? AND claimed=0', (str(args.get('delivery')), uid)).fetchone()
            if not row:
                raise RealmError('That delivery is already claimed or belongs to another player.')
            self._owned(db, uid, row['item_id'], ['courier'])
            db.execute("UPDATE items SET location='vault' WHERE id=?", (row['item_id'],))
            db.execute('UPDATE deliveries SET claimed=1 WHERE id=?', (row['id'],))
            return 'Delivery claimed into your realm vault.'
        if op in ('buy', 'cancel', 'reprice'):
            row = db.execute('SELECT * FROM listings WHERE id=? AND active=1', (str(args.get('listing')),)).fetchone()
            if not row:
                raise RealmError('That listing is no longer available.')
            item = self._owned(db, row['seller'], row['item_id'], ['listing'])
            if op == 'buy':
                if args.get('expected_price') != row['price']:
                    raise RealmError('The listing price changed. Refresh and confirm its current price before buying.')
                if row['seller'] == uid:
                    raise RealmError('You cannot buy your own listing.')
                self._idle(db, row['seller'])
                buyer, seller = self._player(db, uid), self._player(db, row['seller'])
                if buyer.gold < row['price']:
                    raise RealmError('Not enough realm gold.')
                buyer.gold -= row['price']
                seller.gold += row['price']
                self._save_player(db, uid, buyer)
                self._save_player(db, row['seller'], seller)
                db.execute("UPDATE items SET owner=?,location='vault' WHERE id=?", (uid, row['item_id']))
                name = json.loads(item['payload'])['name']
                self._record(db, uid, self._name(db, row['seller']), 'Bought', -row['price'], name)
                self._record(db, row['seller'], self._name(db, uid), 'Sold', row['price'], name)
            else:
                if row['seller'] != uid:
                    raise RealmError('Only the seller can change this listing.')
                if op == 'reprice':
                    price = integer(args.get('price'), 1, 1_000_000)
                    db.execute('UPDATE listings SET price=? WHERE id=?', (price, row['id']))
                    return 'Price updated.'
                db.execute("UPDATE items SET location='vault' WHERE id=?", (row['item_id'],))
            db.execute('UPDATE listings SET active=0 WHERE id=?', (row['id'],))
            return 'Purchase complete. Item delivered to your realm vault.' if op == 'buy' else 'Listing returned to your realm vault.'
        if op.startswith('party_'):
            return self._party_command(db, uid, op[6:], args)
        if op.startswith('guild_'):
            return self._guild_command(db, uid, op[6:], args)
        if op == 'chat':
            self._limit(uid, 'chat', 10)
            body = str(args.get('body', '')).strip()
            if not 1 <= len(body) <= 220 or any(ord(c) < 32 for c in body):
                raise RealmError('Messages must be 1-220 characters, without control characters.')
            channel = 'town'
            if args.get('channel') == 'guild':
                row = db.execute('SELECT guild_id FROM guild_members WHERE user_id=?', (uid,)).fetchone()
                if not row:
                    raise RealmError('Join a guild before using its private channel.')
                channel = 'guild:' + row[0]
            db.execute('INSERT INTO messages(user_id,channel,body,created) VALUES (?,?,?,?)', (uid, channel, body, self.clock()))
            db.execute('DELETE FROM messages WHERE id NOT IN (SELECT id FROM messages ORDER BY id DESC LIMIT 5000)')
            return 'Message sent.'
        raise RealmError('Unknown realm command.')

    @staticmethod
    def _name(db, uid):
        return db.execute('SELECT name FROM users WHERE id=?', (uid,)).fetchone()[0]

    def _party_command(self, db, uid, op, args):
        if op == 'vote':
            integer(args.get('choice'), 0, 2)
        if op == 'tank' and type(args.get('enabled')) is not bool:
            raise RealmError('Choose Tank ON or OFF.')
        party = self._party(db, uid)
        if op in ('create', 'join'):
            if party:
                raise RealmError('Leave your current party first.')
            if self._player(db, uid).level < 45:
                raise RealmError('Shared Labyrinth expeditions unlock at level 45.')
            if op == 'create':
                party = {'id': secrets.token_hex(16), 'code': 'LUX-' + secrets.token_hex(4).upper(), 'leader': uid,
                         'members': [uid], 'ready': [], 'checkpoint': {}}
                db.execute('INSERT INTO parties VALUES (?,?,?)', (party['id'], party['code'], encode(party)))
            else:
                row = db.execute('SELECT id,code,data FROM parties WHERE code=?', (str(args.get('code', '')).strip().upper(),)).fetchone()
                if not row:
                    raise RealmError('No party found for that invitation code.')
                party = dict(json.loads(row['data']), id=row['id'], code=row['code'])
                if party['checkpoint'] or len(party['members']) >= 5:
                    raise RealmError('That party has departed or is full.')
                party['members'].append(uid)
            db.execute('INSERT INTO party_members VALUES (?,?)', (uid, party['id']))
            self._store_party(db, party)
            return 'Party opened. Share the invitation code with up to four friends.' if op == 'create' else 'Party joined.'
        if not party:
            raise RealmError('Open or join a party first.')
        if op == 'leave':
            if party['checkpoint']:
                # End the checkpoint for everyone before unlocking any inventories.
                party['checkpoint'] = {}
                party['ready'] = []
            party['members'].remove(uid)
            party['ready'] = [p for p in party['ready'] if p != uid]
            db.execute('DELETE FROM party_members WHERE user_id=?', (uid,))
            if party['members']:
                if uid == party['leader']:
                    party['leader'] = party['members'][0]
                self._store_party(db, party)
            else:
                db.execute('DELETE FROM parties WHERE id=?', (party['id'],))
            return 'You left. Any active expedition ended for the party; earned rewards were kept.'
        if op == 'ready':
            if party['checkpoint']:
                raise RealmError('The party has already departed.')
            party['ready'] = [p for p in party['ready'] if p != uid] + ([] if uid in party['ready'] else [uid])
        elif op in ('start', 'move', 'ability', 'tank', 'vote', 'refresh'):
            if op in ('start', 'move') and uid != party['leader']:
                raise RealmError('Only the party leader controls movement and departure.')
            if op == 'start' and (party['checkpoint'] or set(party['ready']) != set(party['members'])):
                raise RealmError('Everyone must be ready before departure.')
            if op != 'start' and not party['checkpoint']:
                raise RealmError('The expedition has not started.')
            players = {member: self._player(db, member) for member in party['members']}
            party, players = self.rules.advance(party, players, uid, op, args)
            for member, player in players.items():
                self._save_player(db, member, player)
        else:
            raise RealmError('Unknown party action.')
        self._store_party(db, party)
        return 'Party updated.'

    def _guild_command(self, db, uid, op, args):
        member = db.execute('SELECT g.* FROM guilds g JOIN guild_members m ON m.guild_id=g.id WHERE m.user_id=?', (uid,)).fetchone()
        if op in ('create', 'join'):
            if member:
                raise RealmError('Leave your current guild first.')
            if op == 'create':
                gid, code = secrets.token_hex(16), 'G-' + secrets.token_hex(5).upper()
                db.execute('INSERT INTO guilds VALUES (?,?,?,?)', (gid, code, uid, label(args.get('name', ''))))
            else:
                row = db.execute('SELECT id FROM guilds WHERE code=?', (str(args.get('code', '')).strip().upper(),)).fetchone()
                if not row:
                    raise RealmError('No guild found for that invitation code.')
                gid = row[0]
            db.execute('INSERT INTO guild_members VALUES (?,?)', (uid, gid))
            return 'Guild created.' if op == 'create' else 'Guild joined.'
        if op != 'leave' or not member:
            raise RealmError('No guild membership to change.')
        if member['leader'] == uid:
            if db.execute('SELECT COUNT(*) FROM guild_members WHERE guild_id=?', (member['id'],)).fetchone()[0] > 1:
                raise RealmError('The guild leader cannot leave while other members remain.')
            db.execute('DELETE FROM guilds WHERE id=?', (member['id'],))
        db.execute('DELETE FROM guild_members WHERE user_id=?', (uid,))
        return 'Guild membership ended.'

    def snapshot(self, token, previous=None):
        with self.connection() as db:
            uid = self._user(db, token)
            revision = db.execute('SELECT revision FROM meta').fetchone()[0]
            if str(previous) == str(revision):
                return None
            p = self._player(db, uid)
            account = db.execute('SELECT name,code,kit FROM users WHERE id=?', (uid,)).fetchone()
            items = [{'id': r['id'], 'location': r['location'], 'item': json.loads(r['payload'])}
                     for r in db.execute('SELECT * FROM items WHERE owner=? ORDER BY id LIMIT 500', (uid,)) if r['location'] != 'listing']
            listings = [{'id': r['id'], 'seller_id': r['seller'], 'seller': r['name'], 'price': r['price'], 'item': json.loads(r['payload'])}
                        for r in db.execute('SELECT l.*,i.payload,u.name FROM listings l JOIN items i ON i.id=l.item_id JOIN users u ON u.id=l.seller WHERE active=1 ORDER BY created DESC LIMIT 100')]
            deliveries = [{'id': r['id'], 'sender': r['name'], 'item': json.loads(r['payload'])}
                          for r in db.execute('SELECT d.*,i.payload,u.name FROM deliveries d JOIN items i ON i.id=d.item_id JOIN users u ON u.id=d.sender WHERE recipient=? AND claimed=0 LIMIT 100', (uid,))]
            ledger = [dict(row) for row in db.execute('SELECT other,kind,gold,item,created FROM ledger WHERE user_id=? ORDER BY id DESC LIMIT 80', (uid,))]
            guild = db.execute('SELECT g.* FROM guilds g JOIN guild_members m ON g.id=m.guild_id WHERE m.user_id=?', (uid,)).fetchone()
            guild_data = dict(guild) if guild else None
            if guild_data:
                guild_data['members'] = [dict(row) for row in db.execute('SELECT u.id,u.name FROM guild_members m JOIN users u ON u.id=m.user_id WHERE guild_id=? LIMIT 100', (guild['id'],))]
            channel = 'guild:' + guild['id'] if guild else ''
            messages = [dict(row) for row in db.execute('SELECT m.id,u.name,m.channel,m.body,m.created FROM messages m JOIN users u ON u.id=m.user_id WHERE channel IN (?,?) ORDER BY m.id DESC LIMIT 50', ('town', channel))]
            ladder = [dict(row) for row in db.execute('SELECT id,name,class,level,wins FROM users ORDER BY level DESC,wins DESC,name LIMIT 50')]
            party = self._party(db, uid)
            if party:
                party = copy.deepcopy(party)
                party['profiles'] = [{'id': member, 'name': self._name(db, member), 'player': self._player(db, member).to_dict()} for member in party['members']]
                for profile in party['profiles']:
                    profile['player'].pop('inventory', None)
                    profile['player'].pop('gold', None)
                # Combat snapshots stay on the authority, not other clients.
                checkpoint = party.get('checkpoint', {})
                for row in checkpoint.get('members', []):
                    row.pop('profile_snapshot', None)
                    row.pop('combat_snapshot', None)
                checkpoint.get('session', {}).get('pending_encounter', {}).pop('party_state', None)
            public_player = p.to_dict()
            public_player.pop('inventory', None)
            return {'revision': revision, 'sandbox': self.sandbox, 'user': uid, 'name': account['name'], 'code': account['code'],
                    'kit': bool(account['kit']), 'player': public_player, 'items': items, 'listings': listings,
                    'deliveries': deliveries, 'ledger': ledger, 'guild': guild_data, 'messages': list(reversed(messages)),
                    'ladder': ladder, 'party': party}
