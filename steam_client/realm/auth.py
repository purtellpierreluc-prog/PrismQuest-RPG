"""Server-only Steam ticket verification. No publisher credentials in the client."""

import logging
import re

import httpx

from .service import RealmError


class SteamVerifier:
    def __init__(self, app_id, publisher_key, *, identity='prismquest-realm', transport=None):
        if not str(app_id).isdigit() or int(app_id) <= 0 or int(app_id) == 480 or not publisher_key:
            raise ValueError('A real owned Steam App ID and server-only publisher key are required.')
        self.app_id, self.key, self.identity = int(app_id), publisher_key, identity
        self.transport = transport
        # httpx logs the complete GET URL at INFO; Steam requires credentials in
        # its query. This server-side path must never enable those wire logs.
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('httpcore').setLevel(logging.WARNING)

    async def verify(self, ticket):
        if not re.fullmatch(r'[a-fA-F0-9]{32,16384}', str(ticket)) or len(ticket) % 2:
            raise RealmError('Invalid Steam authentication ticket.')
        try:
            # Do not raise/log HTTPStatusError: its URL contains credentials.
            async with httpx.AsyncClient(transport=self.transport, timeout=10, follow_redirects=False, trust_env=False) as client:
                response = await client.get('https://partner.steam-api.com/ISteamUserAuth/AuthenticateUserTicket/v1/',
                                            params={'key': self.key, 'appid': self.app_id, 'ticket': ticket, 'identity': self.identity})
            if response.status_code != 200:
                raise RealmError('Steam verification is temporarily unavailable. Try again later.')
            data = response.json().get('response', {}).get('params', {})
            steam_id = str(data.get('steamid', ''))
            if data.get('result') != 'OK' or not re.fullmatch(r'\d{17}', steam_id) or data.get('publisherbanned'):
                raise RealmError('Steam did not authorize this account for the realm.')
            return 'steam:' + steam_id
        except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
            if isinstance(exc, RealmError):
                raise
            raise RealmError('Steam verification failed. No local or online progress was changed.') from None
