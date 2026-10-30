"""Realm invariants, hostile requests and two-player network flows."""

import asyncio
import copy
import json
import secrets
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest

from steam_client.realm.api import create_app
from steam_client.realm.auth import SteamVerifier
from steam_client.realm.client import RealmClient
from steam_client.realm.rules import Rules
from steam_client.realm.service import Realm, RealmError

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='session')
def realm_rules():
    return Rules(ROOT)


@pytest.fixture
def realm(tmp_path, realm_rules):
    return Realm(tmp_path / 'realm.sqlite3', realm_rules)


def cmd(realm, token, op, **args):
    return realm.command(token, secrets.token_hex(16), op, args)


def players(realm, count=2, kit=True):
    tokens = [realm.login('sandbox:test-' + str(index), 'Tester ' + str(index)) for index in range(count)]
    if kit:
        for token in tokens:
            cmd(realm, token, 'test_kit')
    return tokens


def item_in(realm, token, location='pack'):
    return next(row for row in realm.snapshot(token)['items'] if row['location'] == location)


def test_preview_loads_private_rules_without_changing_directory_or_desktop_state(realm_rules, game):
    assert not realm_rules.game.DESKTOP_MODE
    assert realm_rules.game.DESKTOP_PATHS is None
    assert realm_rules.game.SUPABASE_URL == ''
    assert realm_rules.game.random is not game.random


def test_relogin_preserves_character_and_does_not_accept_local_snapshots(realm):
    token = players(realm, 1)[0]
    before = realm.snapshot(token)
    relogin = realm.login('sandbox:test-0', 'Hacker', 'Night Angel')
    after = realm.snapshot(relogin)
    assert after['user'] == before['user']
    assert after['name'] == before['name']
    assert after['player'] == before['player']
    with pytest.raises(RealmError):
        cmd(realm, token, 'upload', player={'gold': 1_000_000})
    assert 'inventory' not in after['player']


@pytest.mark.parametrize('bad', [-1, 0, 1.2, True, '10', 1_000_001])
def test_listing_price_is_validated_and_item_kept(realm, bad):
    token = players(realm, 1)[0]
    before = realm.snapshot(token)
    with pytest.raises(RealmError):
        cmd(realm, token, 'list', item=item_in(realm, token)['id'], price=bad)
    assert realm.snapshot(token) == before


def test_buy_reprice_ledger_gold_and_ownership_are_atomic(realm):
    seller, buyer = players(realm)
    item = item_in(realm, seller)
    gold = sum(realm.snapshot(token)['player']['gold'] for token in (seller, buyer))
    cmd(realm, seller, 'list', item=item['id'], price=200)
    listing = realm.snapshot(buyer)['listings'][0]
    cmd(realm, seller, 'reprice', listing=listing['id'], price=321)
    key = secrets.token_hex(16)
    result = realm.command(buyer, key, 'buy', {'listing': listing['id'], 'expected_price': 321})
    assert realm.command(buyer, key, 'buy', {'listing': listing['id'], 'expected_price': 321}) == result
    assert item['id'] not in [r['id'] for r in realm.snapshot(seller)['items']]
    assert item['id'] in [r['id'] for r in realm.snapshot(buyer)['items'] if r['location'] == 'vault']
    assert sum(realm.snapshot(t)['player']['gold'] for t in (seller, buyer)) == gold
    assert realm.snapshot(seller)['ledger'][0]['gold'] == 321
    assert realm.snapshot(buyer)['ledger'][0]['gold'] == -321
    with pytest.raises(RealmError):
        realm.command(buyer, key, 'cancel', {'listing': listing['id']})


def test_two_buyers_cannot_both_buy_an_item(realm):
    seller, one, two = players(realm, 3)
    item = item_in(realm, seller)
    cmd(realm, seller, 'list', item=item['id'], price=100)
    listing = realm.snapshot(seller)['listings'][0]
    second_authority = Realm(realm.path, realm.rules)
    def buy(pair):
        authority, token = pair
        try:
            cmd(authority, token, 'buy', listing=listing['id'], expected_price=100)
            return True
        except RealmError:
            return False
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(buy, [(realm, one), (second_authority, two)]))
    assert sum(results) == 1
    assert sum(item['id'] in [r['id'] for r in realm.snapshot(t)['items']] for t in (seller, one, two)) == 1


def test_insufficient_gold_and_wrong_owner_leave_everything_unchanged(realm):
    seller, buyer = players(realm)
    item = item_in(realm, seller)
    with pytest.raises(RealmError):
        cmd(realm, buyer, 'deposit', item=item['id'])
    cmd(realm, seller, 'list', item=item['id'], price=1_000_000)
    listing = realm.snapshot(seller)['listings'][0]
    before = [realm.snapshot(t) for t in (seller, buyer)]
    with pytest.raises(RealmError):
        cmd(realm, buyer, 'buy', listing=listing['id'], expected_price=1_000_000)
    assert [realm.snapshot(t) for t in (seller, buyer)] == before
    with pytest.raises(RealmError):
        cmd(realm, buyer, 'cancel', listing=listing['id'])
    cmd(realm, seller, 'cancel', listing=listing['id'])
    assert item['id'] == item_in(realm, seller, 'vault')['id']


def test_courier_claim_is_private_and_exactly_once(realm):
    sender, recipient, outsider = players(realm, 3)
    item = item_in(realm, sender)
    code = realm.snapshot(recipient)['code']
    cmd(realm, sender, 'send', item=item['id'], code=code)
    delivery = realm.snapshot(recipient)['deliveries'][0]
    with pytest.raises(RealmError):
        cmd(realm, outsider, 'claim', delivery=delivery['id'])
    cmd(realm, recipient, 'claim', delivery=delivery['id'])
    with pytest.raises(RealmError):
        cmd(realm, recipient, 'claim', delivery=delivery['id'])
    assert len([r for r in realm.snapshot(recipient)['items'] if r['id'] == item['id']]) == 1
    assert not realm.snapshot(recipient)['deliveries']


def test_guild_messages_are_not_visible_to_outsiders(realm):
    founder, member, outsider = players(realm, 3, kit=False)
    cmd(realm, founder, 'guild_create', name='Prism Keepers')
    code = realm.snapshot(founder)['guild']['code']
    cmd(realm, member, 'guild_join', code=code)
    cmd(realm, member, 'chat', body='Private guild strategy', channel='guild')
    assert any(row['body'] == 'Private guild strategy' for row in realm.snapshot(founder)['messages'])
    assert not realm.snapshot(outsider)['messages']
    cmd(realm, member, 'guild_leave')
    assert not realm.snapshot(member)['messages']
    with pytest.raises(RealmError):
        cmd(realm, outsider, 'chat', body='Unauthorized', channel='guild')


def test_party_ready_shared_maze_reconnect_and_gear_lock(realm):
    leader, member = players(realm)
    uid = realm.snapshot(leader)['user']
    cmd(realm, leader, 'party_create')
    code = realm.snapshot(leader)['party']['code']
    cmd(realm, member, 'party_join', code=code)
    with pytest.raises(RealmError):
        cmd(realm, leader, 'party_start')
    cmd(realm, leader, 'party_ready')
    cmd(realm, member, 'party_ready')
    cmd(realm, leader, 'party_start')
    start = realm.snapshot(leader)['party']['checkpoint']
    assert start['session']['status'] == 'exploring'
    assert start['session']['leader_user_id'] == uid
    assert len(start['members']) == 2
    assert 'party_state' not in start['session']['pending_encounter']
    assert all('inventory' not in row['player'] for row in realm.snapshot(member)['party']['profiles'])
    for op in ('arena', 'recover', 'allocate', 'deposit'):
        with pytest.raises(RealmError):
            cmd(realm, leader, op, item=item_in(realm, leader)['id'])
    with pytest.raises((RealmError, ValueError)):
        cmd(realm, member, 'party_move', direction='up')
    cmd(realm, leader, 'party_move', direction='up')
    checkpoint = realm.snapshot(leader)['party']['checkpoint']
    assert checkpoint['session']['current_y'] == start['session']['current_y'] - 1
    assert checkpoint == realm.snapshot(member)['party']['checkpoint']
    realm.logout(member)
    restored = realm.login('sandbox:test-1', 'Changed Name')
    assert realm.snapshot(restored)['party']['checkpoint'] == checkpoint
    with pytest.raises(RealmError):
        realm.snapshot(member)
    cmd(realm, restored, 'party_leave')
    assert not realm.snapshot(leader)['party']['checkpoint']


def test_five_member_limit_and_low_level_gate(realm):
    tokens = players(realm, 6)
    cmd(realm, tokens[0], 'party_create')
    code = realm.snapshot(tokens[0])['party']['code']
    for token in tokens[1:5]:
        cmd(realm, token, 'party_join', code=code)
    with pytest.raises(RealmError):
        cmd(realm, tokens[5], 'party_join', code=code)
    low = realm.login('sandbox:low', 'Low Level')
    with pytest.raises(RealmError):
        cmd(realm, low, 'party_create')


def test_rollback_preserves_items_after_internal_failure(realm):
    token = players(realm, 1)[0]
    before = realm.snapshot(token)
    with realm.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        player = realm._player(db, before['user'])
        player.inventory.pop()
        with pytest.raises(RealmError, match='conservation'):
            realm._save_player(db, before['user'], player)
        db.execute('ROLLBACK')
    assert realm.snapshot(token) == before


def test_sandbox_bypass_and_test_kit_fail_closed_in_live_realm(tmp_path, realm_rules):
    live = Realm(tmp_path / 'live.sqlite3', realm_rules, sandbox=False)
    token = live.login('steam:76561190000000000', 'Verified Player')
    with pytest.raises(RealmError):
        cmd(live, token, 'test_kit')
    with pytest.raises(ValueError):
        create_app(live, sandbox_key='key')
    with pytest.raises(ValueError):
        create_app(live)


def test_http_two_client_trade_and_conditional_snapshot(realm):
    async def scenario():
        transport = httpx.ASGITransport(app=create_app(realm, sandbox_key='developer-only-key'))
        one = RealmClient(url='http://127.0.0.1:8766', transport=transport)
        two = RealmClient(url='http://127.0.0.1:8766', transport=transport)
        await one.connect('HTTP One', 'Black Guard', '1' * 48, key='developer-only-key')
        await two.connect('HTTP Two', 'Night Angel', '2' * 48, key='developer-only-key')
        await one.command('test_kit')
        await two.command('test_kit')
        await one.refresh()
        assert not await one.refresh()
        entry = next(r for r in one.data['items'] if r['location'] == 'pack')
        await one.command('list', {'item': entry['id'], 'price': 123})
        await two.refresh()
        await two.command('buy', {'listing': two.data['listings'][0]['id'], 'expected_price': 123})
        await one.refresh()
        assert one.data['ledger'][0]['gold'] == 123
        assert two.data['ledger'][0]['gold'] == -123
        assert not one.pending and not two.pending
    asyncio.run(scenario())


def test_api_rejects_origins_bad_key_and_large_bodies(realm):
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(realm, sandbox_key='correct')), base_url='http://test') as client:
            bad = await client.post('/v1/session', json={'name': 'One', 'credential': 'a' * 48, 'key': 'wrong'})
            assert bad.status_code == 409
            assert (await client.get('/v1/health', headers={'Origin': 'https://evil.invalid'})).status_code == 403
            assert (await client.post('/v1/session', content='x' * 25000)).status_code == 409
            assert (await client.get('/v1/snapshot')).status_code == 409
    asyncio.run(scenario())


@pytest.mark.parametrize('url', ['http://example.com', 'https://user:password@example.com', 'https://example.com/?key=x', 'file:///tmp/test'])
def test_client_rejects_unsafe_origins(url):
    with pytest.raises(ValueError):
        RealmClient(url=url)


def test_steam_verification_accepts_only_server_verified_identity():
    async def scenario():
        def handler(request):
            assert request.url.params['appid'] == '123456'
            assert request.url.params['identity'] == 'prismquest-realm'
            return httpx.Response(200, json={'response': {'params': {'result': 'OK', 'steamid': '76561190000000000'}}})
        verifier = SteamVerifier(123456, 'server-secret', transport=httpx.MockTransport(handler))
        assert await verifier.verify('ab' * 64) == 'steam:76561190000000000'
        with pytest.raises(RealmError):
            await verifier.verify('not-a-ticket')
        denied = SteamVerifier(123456, 'server-secret', transport=httpx.MockTransport(lambda request: httpx.Response(200, json={'response': {'params': {'result': 'Fail'}}})))
        with pytest.raises(RealmError):
            await denied.verify('ab' * 64)
    asyncio.run(scenario())
    for app_id, key in [(0, 'key'), (480, 'key'), ('', 'key'), (123456, '')]:
        with pytest.raises(ValueError):
            SteamVerifier(app_id, key)


def test_lost_reply_retries_same_idempotent_command(realm):
    async def scenario():
        client = RealmClient(service=realm)
        await client.connect('Retry Tester', 'Black Guard', 'r' * 48)
        await client.command('test_kit')
        entry = next(row for row in client.data['items'] if row['location'] == 'pack')
        pending = {'key': secrets.token_hex(16), 'operation': 'deposit', 'args': {'item': entry['id']}}
        realm.command(client.token, **pending)
        client.pending = copy.deepcopy(pending)
        with pytest.raises(RealmError, match='Retry the pending'):
            await client.command('test_kit')
        await client.command()
        assert client.pending is None
        assert len([r for r in client.data['items'] if r['id'] == entry['id'] and r['location'] == 'vault']) == 1
    asyncio.run(scenario())


def test_sessions_are_hashed_and_expire(realm):
    token = players(realm, 1, kit=False)[0]
    with realm.connection() as db:
        assert token not in json.dumps([tuple(row) for row in db.execute('SELECT * FROM sessions')])
    realm.clock = lambda: 9_999_999_999
    with pytest.raises(RealmError, match='expired'):
        realm.snapshot(token)


def test_price_change_requires_a_new_buyer_confirmation(realm):
    seller, buyer = players(realm)
    cmd(realm, seller, 'list', item=item_in(realm, seller)['id'], price=100)
    listing = realm.snapshot(buyer)['listings'][0]
    cmd(realm, seller, 'reprice', listing=listing['id'], price=200)
    before = realm.snapshot(buyer)
    with pytest.raises(RealmError, match='price changed'):
        cmd(realm, buyer, 'buy', listing=listing['id'], expected_price=100)
    assert realm.snapshot(buyer) == before


def test_boss_grants_one_level_and_prism_gold_once_to_every_member(realm, monkeypatch):
    leader, member = players(realm)
    cmd(realm, leader, 'party_create')
    cmd(realm, member, 'party_join', code=realm.snapshot(leader)['party']['code'])
    for token in (leader, member):
        cmd(realm, token, 'party_ready')
    cmd(realm, leader, 'party_start')
    g = realm.rules.game
    original = g._generate_labyrinth_monster
    def harmless(*args, **kwargs):
        monster, xp = original(*args, **kwargs)
        monster.hp = monster.max_hp = 1
        monster.evasion = 0
        monster.armor = 0
        monster.magic_resist = 0
        return monster, xp
    monkeypatch.setattr(g, '_generate_labyrinth_monster', harmless)
    # Seed a final tile in an otherwise cleared persisted maze. This exercises
    # the actual boss, rewards, two-player vote and next-floor orchestration.
    with realm.connection() as db:
        party = realm._party(db, realm.snapshot(leader)['user'])
        session = party['checkpoint']['session']
        session['tile_states'] = {f'{x},{y}': {'visited': True, 'resolved': True, 'kind': 'free'} for x in range(7) for y in range(7)}
        session['tile_states']['3,2'] = {'visited': False, 'resolved': False, 'kind': 'free'}
        realm._store_party(db, party)
    cmd(realm, leader, 'party_move', direction='up')
    assert realm.snapshot(leader)['party']['checkpoint']['session']['status'] == 'reward'
    assert [realm.snapshot(token)['player']['level'] for token in (leader, member)] == [46, 46]
    assert all(realm.snapshot(token)['player']['gold'] >= 2100 for token in (leader, member))
    with realm.connection() as db:
        party = realm._party(db, realm.snapshot(leader)['user'])
        for reward in party['checkpoint']['session']['reward_options']:
            reward['effects'] = {'instant_gold_flat': 37}
        realm._store_party(db, party)
    gold_before = [realm.snapshot(token)['player']['gold'] for token in (leader, member)]
    cmd(realm, leader, 'party_vote', choice=0)
    cmd(realm, member, 'party_vote', choice=0)
    assert [realm.snapshot(token)['player']['gold'] for token in (leader, member)] == [amount + 37 for amount in gold_before]
    session = realm.snapshot(leader)['party']['checkpoint']['session']
    assert session['floor'] == 2 and session['status'] == 'exploring'
    cmd(realm, member, 'party_refresh')
    assert [realm.snapshot(token)['player']['gold'] for token in (leader, member)] == [amount + 37 for amount in gold_before]


def test_pending_action_survives_client_restart(realm, tmp_path):
    async def scenario():
        pending_path = tmp_path / 'pending.json'
        client = RealmClient(service=realm, pending_path=pending_path)
        await client.connect('Persistent Retry', 'Black Guard', 'r' * 48)
        client.pending = {'key': secrets.token_hex(16), 'operation': 'test_kit', 'args': {}}
        client._save_pending()
        realm.command(client.token, **client.pending)
        restored = RealmClient(service=realm, pending_path=pending_path)
        await restored.connect('Persistent Retry', 'Black Guard', 'r' * 48)
        await restored.command()
        assert restored.pending is None
        assert restored.data['kit']
        assert json.loads(pending_path.read_text()) is None
    asyncio.run(scenario())


def test_headless_expedition_never_reads_or_writes_browser_storage(realm_rules, monkeypatch):
    monkeypatch.setattr(realm_rules.game, 'app', object())
    player = realm_rules.create('Isolated Hero', 'Black Guard')
    state = realm_rules.state('isolated-identity', player)
    assert state.player is player
    assert state.screen == 'game'
    assert state._stored_runtime_session() == {}
    assert realm_rules.game._image_path_to_data_uri(str(ROOT / 'Assets')) == ''
    assert realm_rules.game.get_masterquest_essence_variant_data_uris() == {'blue': ''}


def test_equipping_preserves_unique_item_ids_and_returns_previous_piece(realm):
    token = players(realm, 1)[0]
    uid = realm.snapshot(token)['user']
    g = realm.rules.game
    with realm.connection() as db:
        p = realm._player(db, uid)
        p.inventory.append(g.generate_specific_item(45, 'weapon', 'Axe', 'Rare'))
        realm._save_player(db, uid, p)
    before = realm.snapshot(token)
    entry = next(r for r in before['items'] if r['location'] == 'pack' and r['item']['rarity'] == 'Rare' and r['item']['subtype'] == 'Axe')
    old = next(r for r in before['items'] if r['location'] == 'equip:weapon')
    cmd(realm, token, 'equip', item=entry['id'])
    after = realm.snapshot(token)
    assert sorted(r['id'] for r in before['items']) == sorted(r['id'] for r in after['items'])
    assert next(r for r in after['items'] if r['id'] == old['id'])['location'] == 'pack'
    assert next(r for r in after['items'] if r['id'] == entry['id'])['location'] == 'equip:weapon'
    assert after['player']['equipped']['weapon'] == entry['item']


def test_deposit_withdraw_keep_ids_after_service_restart(realm):
    token = players(realm, 1)[0]
    entry = item_in(realm, token)
    cmd(realm, token, 'deposit', item=entry['id'])
    restored = Realm(realm.path, realm.rules)
    cmd(restored, token, 'withdraw', item=entry['id'])
    assert next(r for r in restored.snapshot(token)['items'] if r['id'] == entry['id']) == entry
