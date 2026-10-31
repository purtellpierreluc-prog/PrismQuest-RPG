import asyncio

import pytest

from steam_client.refresh import RefreshQueue


class Scheduler:
    def __init__(self):
        self.now = 10.0
        self.calls = []
        self.fail = False

    def later(self, delay, callback):
        if self.fail:
            raise RuntimeError('panel removed')
        handle = type('Handle', (), {'cancelled': False, 'cancel': lambda h: setattr(h, 'cancelled', True)})()
        self.calls.append((self.now+delay, callback, handle))
        return handle

    def advance(self, seconds=1):
        self.now += seconds
        due, self.calls = self.calls, []
        for at, callback, handle in due:
            if not handle.cancelled and at <= self.now:
                callback()
            elif not handle.cancelled:
                self.calls.append((at, callback, handle))


def queue_for(render=lambda: None, alive=lambda: True, error=lambda exc: None):
    scheduler = Scheduler()
    queue = RefreshQueue(render, scheduler.later, lambda: scheduler.now, alive, error)
    return queue, scheduler


def test_burst_refresh_reads_latest_state_once_without_polling():
    state, seen = {'page': 'town'}, []
    queue, scheduler = queue_for(lambda: seen.append(state['page']))
    queue.request()
    for page in ['pack','town','market','settings']:
        state['page'] = page
        queue.request()
    assert queue.pending and len(scheduler.calls) == 1
    scheduler.advance()
    assert seen == ['town', 'settings']
    assert not queue.pending and not scheduler.calls


def test_scheduler_failure_never_poison_pending_flag():
    queue, scheduler = queue_for()
    queue.request()
    scheduler.fail = True
    queue.request()
    assert not queue.pending
    scheduler.fail = False
    queue.request()
    scheduler.advance()
    assert queue.renders == 2 and not queue.pending


def test_render_exception_can_recover_with_another_request():
    seen, errors = [], []
    def render():
        seen.append(1)
        if len(seen) == 1:
            raise RuntimeError('bad view')
    queue, scheduler = queue_for(render, error=errors.append)
    queue.request()
    assert len(errors) == 1 and not queue.pending
    queue.request()
    scheduler.advance()
    assert len(seen) == 2 and queue.errors == 1 and not queue.pending


def test_force_invalidates_old_callback_even_if_it_already_queued():
    queue, scheduler = queue_for()
    queue.request()
    queue.request()
    stale = scheduler.calls[0][1]
    queue.request(force=True)
    stale()
    assert queue.renders == 2 and not queue.pending


def test_render_request_from_inside_render_is_deferred_not_recursive():
    seen = []
    def render():
        seen.append(1)
        if len(seen) == 1:
            queue.request(force=True)
    queue, scheduler = queue_for(render)
    queue.request()
    assert len(seen) == 1 and queue.pending
    scheduler.advance()
    assert len(seen) == 2 and not queue.pending


@pytest.mark.parametrize('delete', [True,False])
def test_old_page_never_renders_after_deletion_or_close(delete):
    live = [True]
    queue, scheduler = queue_for(alive=lambda: live[0])
    queue.request()
    queue.request()
    if delete:
        live[0] = False
    else:
        queue.close()
    scheduler.advance()
    assert queue.renders == 1 and not queue.pending


def test_async_refresh_is_awaited_and_errors_do_not_leave_a_lock():
    errors, entered = [], []
    async def render():
        entered.append(1)
        await asyncio.sleep(0)
        if len(entered) == 1:
            raise RuntimeError('async renderer failed')
    queue, scheduler = queue_for(render, error=errors.append)
    async def exercise():
        queue.request()
        assert queue.rendering
        queue.request(force=True)
        await asyncio.sleep(.01)
        assert not queue.rendering and queue.pending and len(errors) == 1
        scheduler.advance()
        await asyncio.sleep(.01)
        assert not queue.rendering and not queue.pending and len(entered) == 2
    asyncio.run(exercise())
