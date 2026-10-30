"""Five independent clients against a running loopback sandbox; no solo saves."""

import argparse
import asyncio
import json
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from steam_client.realm.client import RealmClient


async def check(port, key_file):
    url = f'http://127.0.0.1:{port}'
    key = key_file.read_text(encoding='ascii').strip()
    clients = []
    for index in range(5):
        client = RealmClient(url=url)
        await client.connect('Network Tester ' + str(index), 'Night Angel' if index == 1 else 'Black Guard', secrets.token_hex(32), key=key)
        await client.command('test_kit')
        clients.append(client)
    one, two = clients[:2]
    item = next(r for r in one.data['items'] if r['location'] == 'pack')
    await one.command('list', {'item': item['id'], 'price': 123})
    await two.refresh()
    await two.command('buy', {'listing': two.data['listings'][0]['id'], 'expected_price': 123})
    await one.refresh()
    assert one.data['ledger'][0]['gold'] == 123 and two.data['ledger'][0]['gold'] == -123
    await two.command('send', {'item': item['id'], 'code': one.data['code']})
    await one.refresh()
    await one.command('claim', {'delivery': one.data['deliveries'][0]['id']})
    assert any(r['id'] == item['id'] and r['location'] == 'vault' for r in one.data['items'])
    await one.command('guild_create', {'name': 'Network Keepers'})
    await two.command('guild_join', {'code': one.data['guild']['code']})
    await two.command('chat', {'channel': 'guild', 'body': 'Five clients. One authority.'})
    await one.refresh()
    await clients[2].refresh()
    assert any(m['body'] == 'Five clients. One authority.' for m in one.data['messages'])
    assert not clients[2].data['messages']
    await one.command('party_create')
    code = one.data['party']['code']
    for client in clients[1:]:
        await client.command('party_join', {'code': code})
    for client in clients:
        await client.command('party_ready')
    await one.command('party_start')
    await one.command('party_move', {'direction': 'up'})
    checkpoint = one.data['party']['checkpoint']
    for client in clients[1:]:
        await client.refresh()
        assert client.data['party']['checkpoint'] == checkpoint
        assert not await client.refresh()
    await two._http('DELETE', '/v1/session')
    assert len(checkpoint['members']) == 5
    await one.command('party_leave')
    return {'passed': True, 'clients': 5, 'trade': True, 'courier': True, 'guild_privacy': True,
            'shared_expedition': True, 'conditional_snapshots': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--key-file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = asyncio.run(check(args.port, args.key_file))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
