"""Small HTTP boundary: bounded payloads, private sessions, revisioned snapshots."""

import asyncio
import json
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from .service import RealmError


def create_app(realm, *, sandbox_key=None, steam_verifier=None):
    if realm.sandbox != bool(sandbox_key) or (not realm.sandbox and steam_verifier is None) or (sandbox_key and steam_verifier):
        raise ValueError('Choose a keyed sandbox or a Steam-authenticated realm; never both.')
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware('http')
    async def envelope(request, call_next):
        if request.headers.get('origin'):
            return JSONResponse({'error': 'Browser origins are not accepted by the realm API.'}, status_code=403)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.exception_handler(RealmError)
    async def realm_error(_request, error):
        return JSONResponse({'error': str(error)}, status_code=409)

    async def payload(request):
        chunks, size = [], 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > 24000:
                raise RealmError('Request is too large.')
            chunks.append(chunk)
        try:
            body = json.loads(b''.join(chunks))
        except (ValueError, UnicodeError):
            raise RealmError('Invalid request body.') from None
        if not isinstance(body, dict):
            raise RealmError('Invalid request body.')
        return body

    def token(request):
        value = request.headers.get('authorization', '')
        if not value.startswith('Bearer ') or len(value) > 256:
            raise RealmError('A realm session is required.')
        return value[7:]

    @app.get('/v1/health')
    def health():
        return {'protocol': 1, 'sandbox': realm.sandbox, 'authentication': 'sandbox' if realm.sandbox else 'steam'}

    @app.post('/v1/session')
    async def login(request: Request):
        data = await payload(request)
        with realm.lock:
            realm._limit(request.client.host if request.client else 'unknown', 'login', 12)
        if realm.sandbox:
            if not secrets.compare_digest(str(data.get('key', '')), sandbox_key):
                raise RealmError('The test-realm access key is invalid.')
            credential = str(data.get('credential', ''))
            if not 32 <= len(credential) <= 128:
                raise RealmError('A private test-character credential is required.')
            identity = 'sandbox:' + realm._digest(credential)
        else:
            identity = await steam_verifier.verify(data.get('ticket', ''))
        session = await asyncio.to_thread(realm.login, identity, data.get('name', ''), data.get('player_class', 'Black Guard'))
        return {'token': session, 'expires_in': 86400}

    @app.delete('/v1/session')
    def logout(request: Request):
        realm.logout(token(request))
        return Response(status_code=204)

    @app.get('/v1/snapshot')
    def snapshot(request: Request):
        data = realm.snapshot(token(request), request.headers.get('if-none-match', '').strip('"'))
        if data is None:
            return Response(status_code=304)
        return JSONResponse(data, headers={'ETag': f'"{data["revision"]}"'})

    @app.post('/v1/command')
    async def command(request: Request):
        data = await payload(request)
        return await asyncio.to_thread(realm.command, token(request), data.get('key', ''), data.get('operation'), data.get('args'))

    return app
