"""Opt-in clients with no background traffic during normal solo play."""

import asyncio
import hashlib
import json
import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .service import RealmError


class RealmClient:
    def __init__(self, *, service=None, url=None, transport=None, pending_path=None):
        if url:
            parts = urlsplit(url)
            loopback = parts.hostname in ('127.0.0.1', 'localhost', '::1')
            if parts.username or parts.password or parts.query or parts.fragment or parts.path not in ('', '/'):
                raise ValueError('Use a realm origin URL without credentials, path or query.')
            if parts.scheme != 'https' and not (loopback and parts.scheme == 'http'):
                raise ValueError('Non-local realms require HTTPS.')
        self.service, self.url, self.transport = service, url.rstrip('/') if url else None, transport
        self.token = None
        self.data = None
        self.steam_provider = None
        self.pending = None
        self.pending_path = Path(pending_path) if pending_path else None
        if self.pending_path and self.pending_path.exists():
            self.pending = json.loads(self.pending_path.read_text(encoding='utf-8'))
        self.busy = False

    def _save_pending(self):
        if not self.pending_path:
            return
        self.pending_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.pending_path.with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump(self.pending, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.pending_path)

    async def _http(self, method, path, **kwargs):
        headers = kwargs.pop('headers', {})
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        try:
            async with httpx.AsyncClient(base_url=self.url, transport=self.transport, timeout=15,
                                        trust_env=False, follow_redirects=False) as client:
                response = await client.request(method, path, headers=headers, **kwargs)
        except httpx.HTTPError:
            raise RealmError('Connection interrupted. Your realm progress is preserved. Retry the pending action before doing anything else.') from None
        if response.status_code >= 400:
            try:
                message = response.json().get('error', 'The realm rejected that request.')
            except ValueError:
                message = 'The realm could not process that request.'
            raise RealmError(message)
        return None if response.status_code in (204, 304) else response.json()

    async def connect(self, name, player_class, credential, *, key=None, ticket=None):
        if self.service:
            self.token = await asyncio.to_thread(self.service.login, 'sandbox:' + self.service._digest(credential), name, player_class)
        else:
            result = await self._http('POST', '/v1/session', json={'name': name, 'player_class': player_class,
                                                               'credential': credential, 'key': key, 'ticket': ticket})
            self.token = result['token']
        self.data = None
        await self.refresh()

    async def refresh(self):
        if not self.token:
            return False
        revision = self.data['revision'] if self.data else None
        if self.service:
            data = await asyncio.to_thread(self.service.snapshot, self.token, revision)
        else:
            data = await self._http('GET', '/v1/snapshot', headers={'If-None-Match': f'"{revision}"'} if revision is not None else {})
        if data is not None:
            self.data = data
            return True
        return False

    async def command(self, operation=None, args=None):
        if self.busy:
            raise RealmError('An action is already in progress.')
        self.busy = True
        try:
            if self.pending is None:
                self.pending = {'key': secrets.token_hex(16), 'operation': operation, 'args': args or {}}
                self._save_pending()
            elif operation is not None:
                raise RealmError('Retry the pending action first. This prevents a duplicate purchase or transfer.')
            try:
                if self.service:
                    result = await asyncio.to_thread(self.service.command, self.token, **self.pending)
                else:
                    result = await self._http('POST', '/v1/command', json=self.pending)
            except RealmError as exc:
                if not str(exc).startswith(('Connection interrupted.', 'Your realm session expired.')):
                    self.pending = None
                    self._save_pending()
                raise
            self.pending = None
            self._save_pending()
            await self.refresh()
            return result
        finally:
            self.busy = False


class NetworkController:
    def __init__(self, paths):
        self.paths = paths
        self.client = None
        self.tab = 'Expedition'
        self.message = ''
        self.error = False
        self.credentials = paths.data / 'realm-preview-identity.json'
        self.drafts = {}
        self.test_key = None

    def credential(self):
        if self.credentials.exists():
            return json.loads(self.credentials.read_text(encoding='utf-8'))['credential']
        credential = secrets.token_urlsafe(48)
        self.credentials.write_text(json.dumps({'credential': credential}), encoding='utf-8')
        return credential

    async def test_service(self, url, key, name, player_class):
        identity = hashlib.sha256(url.rstrip('/').encode()).hexdigest()[:16]
        client = RealmClient(url=url, pending_path=self.paths.data / 'realm-preview' / ('pending-' + identity + '.json'))
        if urlsplit(url).hostname not in ('127.0.0.1', 'localhost', '::1'):
            raise RealmError('The developer test-service connection is restricted to loopback.')
        await client.connect(name, player_class, self.credential(), key=key)
        self.client = client
        self.test_key = key

    async def reconnect(self):
        if self.client and self.client.data and not self.client.data['sandbox'] and self.client.steam_provider:
            data = self.client.data
            await self.steam(self.client.url, self.client.steam_provider, data['name'], data['player']['player_class'])
            return
        if not self.client or not self.client.data or not self.client.data['sandbox']:
            raise RealmError('Steam authentication must reconnect through its native ticket provider.')
        data = self.client.data
        await self.client.connect(data['name'], data['player']['player_class'], self.credential(), key=self.test_key)

    async def steam(self, url, ticket_provider, name, player_class):
        """The native provider waits for Steam's callback, then cancels its ticket.

        Only the verified backend response supplies the account identity.
        """
        async with ticket_provider.ticket('prismquest-realm') as ticket:
            realm_id = hashlib.sha256(url.rstrip('/').encode()).hexdigest()[:16]
            client = RealmClient(url=url, pending_path=self.paths.data / 'realm-online' / ('pending-' + realm_id + '.json'))
            await client.connect(name, player_class, '', ticket=ticket)
            if client.data['sandbox']:
                raise RealmError('A Steam login cannot attach to a sandbox realm.')
            client.steam_provider = ticket_provider
        self.client = client

    async def preview(self, name, player_class):
        if self.client and self.client.token:
            return
        from .rules import Rules
        from .service import Realm
        credential = self.credential()
        rules = await asyncio.to_thread(Rules, self.paths.resources)
        service = await asyncio.to_thread(Realm, self.paths.data / 'realm-preview' / 'realm.sqlite3', rules)
        self.client = RealmClient(service=service, pending_path=self.paths.data / 'realm-preview' / 'pending-local.json')
        await self.client.connect(name, player_class, credential)
