"""Event-driven refreshes owned by the page, never by replaceable scene slots."""

import asyncio
import inspect
import logging

LOGGER = logging.getLogger(__name__)


class RefreshQueue:
    def __init__(self, render, schedule, clock, alive=lambda: True, on_error=lambda exc: None, interval=.25):
        self.render, self.schedule, self.clock = render, schedule, clock
        self.alive, self.on_error, self.interval = alive, on_error, interval
        self.pending = self.rendering = self.dirty = self.closed = False
        self.handle = None
        self.task = None
        self.last_at = float('-inf')
        self.token = self.renders = self.errors = 0

    def request(self, *, force=False, delay=0):
        if self.closed or not self.alive():
            self.close()
            return
        if self.rendering:
            self.dirty = True
            return
        if self.pending and not force:
            return
        if force:
            self._cancel()
        wait = 0 if force else max(delay, self.interval-(self.clock()-self.last_at), 0)
        self.token += 1
        token = self.token
        if wait == 0:
            self._flush(token)
            return
        self.pending = True
        try:
            self.handle = self.schedule(wait, lambda: self._flush(token))
        except Exception as exc:
            LOGGER.exception('Could not schedule desktop view update.')
            self.pending = False
            self.handle = None
            self._error(exc)

    def _error(self, error):
        self.errors += 1
        try:
            self.on_error(error)
        except Exception:
            LOGGER.exception('Could not show view recovery controls.')

    def _flush(self, token):
        if token != self.token:
            return
        self.pending, self.handle = False, None
        if self.closed or not self.alive():
            self.close()
            return
        self.rendering, self.last_at = True, self.clock()
        self.renders += 1
        try:
            result = self.render()
        except Exception as exc:
            LOGGER.exception('Desktop view update interrupted; queue remains recoverable.')
            self._error(exc)
            self._finish()
        else:
            if inspect.isawaitable(result):
                self.task = asyncio.create_task(self._await_render(result))
            else:
                self._finish()

    async def _await_render(self, result):
        try:
            await result
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            LOGGER.exception('Asynchronous desktop view update interrupted.')
            self._error(exc)
        finally:
            self._finish()

    def _finish(self):
        self.rendering, self.task = False, None
        if self.dirty:
            self.dirty = False
            self.request()

    def _cancel(self):
        self.token += 1
        if self.handle is not None:
            self.handle.cancel()
        self.handle, self.pending = None, False

    def close(self):
        self.closed = True
        self._cancel()
        if self.task is not None:
            self.task.cancel()


def bind_page_refresh(client, render):
    from nicegui import ui

    loop = asyncio.get_running_loop()
    with client:
        with ui.element('aside').classes('pd-view-recovery').props('role=alert') as recovery:
            ui.label('A view update was interrupted. Retry the view without resetting your run.')
            ui.button('Retry View', on_click=lambda: queue.request(force=True)).classes('mq-btn-gold')
        recovery.set_visibility(False)

    async def redraw():
        with client:
            result = render()
            if inspect.isawaitable(result):
                await result
            recovery.set_visibility(False)

    def error(_exc):
        if not client.is_deleted:
            with client:
                recovery.set_visibility(True)

    queue = RefreshQueue(redraw, loop.call_later, loop.time, lambda: not client.is_deleted, error)
    client.on_delete(queue.close)
    return queue
