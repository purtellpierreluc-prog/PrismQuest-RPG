"""Run the standalone realm service, separate from the desktop UI and its saves."""

import argparse
import logging
import os
import secrets
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from steam_client.realm.api import create_app
from steam_client.realm.auth import SteamVerifier
from steam_client.realm.rules import Rules
from steam_client.realm.service import Realm


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sandbox', action='store_true')
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    if args.sandbox and args.host not in ('127.0.0.1', '::1'):
        parser.error('Sandbox authentication is restricted to loopback. Never expose the test realm publicly.')
    args.data_dir.mkdir(parents=True, exist_ok=True)
    key = verifier = None
    if args.sandbox:
        key_file = args.data_dir / 'sandbox-access.key'
        if not key_file.exists():
            key_file.write_text(secrets.token_urlsafe(48), encoding='ascii')
        key = key_file.read_text(encoding='ascii').strip()
    else:
        verifier = SteamVerifier(os.environ.get('PRISMQUEST_STEAM_APP_ID', ''), os.environ.get('PRISMQUEST_STEAM_PUBLISHER_KEY', ''))
    # Steam's documented GET verification URL contains credentials; never emit it.
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    realm = Realm(args.data_dir / 'realm.sqlite3', Rules(ROOT), sandbox=args.sandbox)
    uvicorn.run(create_app(realm, sandbox_key=key, steam_verifier=verifier), host=args.host, port=args.port, access_log=False)


if __name__ == '__main__':
    main()
