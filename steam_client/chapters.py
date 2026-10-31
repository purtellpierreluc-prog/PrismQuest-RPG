"""Decision models for the shop and the rite; existing game rules stay in charge."""

import asyncio
import copy
import json
import logging
import uuid
from dataclasses import dataclass, field

from .transactions import STATE_FIELDS, DesktopTransactionError

LOGGER = logging.getLogger(__name__)


class ChapterError(ValueError):
    pass


def fingerprint(item):
    return json.dumps(item.to_dict(), sort_keys=True, separators=(',', ':'))


def hero_key(state):
    p = state.player
    return (state.active_slot_index, p.name, p.player_class, getattr(state, 'current_run_start_wall_time', 0)) if p else None


@dataclass(frozen=True)
class Purchase:
    key: str
    item: object = field(repr=False, compare=False)
    owned_item: object = field(repr=False, compare=False)
    price: int = 0


class Market:
    def __init__(self, state, game):
        self.state, self.game = state, game
        self.selected = self.armed = self.receipt = None
        self.message = ''

    def select(self, offer):
        if not any(candidate is offer for candidate in self.state.marketplace_offers):
            raise ChapterError('The stock changed. Select a current offer.')
        self.selected, self.armed, self.message = offer, None, ''

    def blocker(self):
        if self.selected is None or not any(candidate is self.selected for candidate in self.state.marketplace_offers):
            return 'Select a curio to inspect it.'
        if self.selected.sold:
            return 'Acquired. This stall restocks at the next level milestone.'
        if self.state.player.gold < self.selected.price:
            return f'You need {self.selected.price:,} gold for this offer.'
        return ''

    def arm(self):
        if self.blocker():
            raise ChapterError(self.blocker())
        self.armed = self.selected, self.selected.price, fingerprint(self.selected.item)

    def buy(self):
        armed, self.armed = self.armed, None
        if not armed:
            raise ChapterError('Review the purchase first.')
        if self.blocker():
            raise ChapterError(self.blocker())
        offer = self.selected
        if offer is not armed[0] or offer.price != armed[1] or fingerprint(offer.item) != armed[2]:
            raise ChapterError('The offer changed. Review its current price and item before buying.')
        index = next(i for i, candidate in enumerate(self.state.marketplace_offers) if candidate is offer)
        self.state.buy_marketplace_offer(index)
        self.receipt = Purchase(uuid.uuid4().hex, copy.deepcopy(offer.item), offer.item, offer.price)
        return self.receipt


PROGRESSION_FIELDS = (
    'ladder_stats', 'unlocked_classes', 'selection_return_class', 'pending_character_name',
    'current_run_started_at', 'current_run_start_wall_time', 'current_monster', 'current_monster_xp',
    'screen', 'game_tab', 'class_select_notice', 'current_run_kills', 'monster_chain_combo',
    'arena_flee_requested', 'mana_regen_progress', 'life_regen_progress', 'arena_combat_log_hidden',
    'current_arena_monster_uri', 'current_arena_monster_species', 'last_arena_monster_uri',
    'last_arena_monster_species', 'current_encounter_type', 'last_encounter_type',
    'current_well_scene_line', 'current_inn_line', 'current_ladder_line', 'class_compendium_open',
    'marketplace_offer_refresh_level', 'marketplace_selected_index', 'marketplace_hovered_index',
    'marketplace_pending_purchase_index', 'current_marketplace_line', 'current_transmute_line', 'transmute_message',
)


def atomic_progress(state, action):
    """Synchronous entry/settlement commits once; a disk failure restores the climb."""
    fields = set(STATE_FIELDS) | set(PROGRESSION_FIELDS) | {key for key in state.__dict__ if key.startswith('masterquest_')}
    snapshot = copy.deepcopy({key: state.__dict__[key] for key in fields if key in state.__dict__})
    originals = {name: (name in state.__dict__, state.__dict__.get(name), getattr(state, name))
                 for name in ('persist_to_disk', 'persist_runtime_session')}
    pending_disk = pending_runtime = force = False
    def defer_disk(*args, **kwargs):
        nonlocal pending_disk, force
        pending_disk, force = True, force or bool(kwargs.get('force'))
    def defer_runtime(*args, **kwargs):
        nonlocal pending_runtime
        pending_runtime = True
    state.persist_to_disk, state.persist_runtime_session = defer_disk, defer_runtime
    try:
        result = action()
        if pending_disk:
            originals['persist_to_disk'][2](force=force)
    except Exception as exc:
        for key in fields:
            if key in snapshot:
                state.__dict__[key] = snapshot[key]
            else:
                state.__dict__.pop(key, None)
        raise DesktopTransactionError('The rite could not be saved. Your previous hero, items, gold and progression were restored. Check storage space and retry.') from exc
    finally:
        for name, (had_override, override, _) in originals.items():
            if had_override:
                state.__dict__[name] = override
            else:
                state.__dict__.pop(name, None)
    if pending_runtime:
        try:
            originals['persist_runtime_session'][2]()
        except Exception:
            LOGGER.exception('Rite saved; transient UI session could not be updated.')
    return result


@dataclass(frozen=True)
class AscensionResult:
    key: str
    passed: bool
    final: bool
    name: str
    player_class: str
    next_class: str
    level: int
    victories: int
    seconds: float
    gold: int
    items: int
    companions: int
    attempts: int


@dataclass
class Offering:
    essence: str
    vessel: str
    correct: bool = field(repr=False)
    applied: bool = False


class Ascension:
    def __init__(self, state, game):
        self.state, self.game = state, game
        self.owner = hero_key(state)
        self.session = uuid.uuid4().hex
        self.started = self.busy = False
        self.acknowledged = True
        self.receipt = None
        self.pending_verdict = None
        self.error = ''
        self.sequence = 0
        self.last_essence = self.last_vessel = ''
        self._before = None
        self.offering = None
        self.target_vessel = ''
        self.history = []
        self.phase = 'ritual'
        self._quick = asyncio.Event()

    def brief(self):
        p, g = self.state.player, self.game
        if p is None:
            raise ChapterError('Open a hero before approaching the prism.')
        order = g.season_class_order(self.state.current_slot_season_id())
        return {'cost': g.masterquest_attempt_cost(p.player_class), 'count': g.masterquest_slot_count(p.player_class),
                'odds': g.masterquest_blind_clear_text(p.player_class), 'next': g.season_class_masterquest_next(self.state.current_slot_season_id()).get(p.player_class, ''),
                'final': p.player_class == order[-1], 'blocker': self.state.masterquest_entry_blocker(), 'path': order}

    def enter(self):
        if self.started or self.receipt:
            raise ChapterError('This rite has already begun.')
        if hero_key(self.state) != self.owner:
            raise ChapterError('The active hero changed. Approach the prism again.')
        brief = self.brief()
        if brief['blocker']:
            raise ChapterError(brief['blocker'])
        atomic_progress(self.state, self.state.begin_masterquest)
        self.started = True

    def select(self, key):
        s = self.state
        if not self.started or self.busy or self.receipt or self.pending_verdict is not None or self.offering:
            raise ChapterError('The prism is not accepting another light yet.')
        if key not in s.masterquest_essence_order or key in s.masterquest_matched_essences:
            raise ChapterError('Choose an unbound light.')
        s.select_masterquest_essence(key)
        s.clear_masterquest_drag()
        self.target_vessel = ''

    def aim(self, vessel):
        s = self.state
        if not self.started or self.busy or self.receipt or self.offering or self.pending_verdict is not None:
            raise ChapterError('The prism is not accepting another choice yet.')
        if vessel not in s.masterquest_container_order or vessel in s.masterquest_matched_containers:
            raise ChapterError('Choose an empty vessel.')
        if not s.masterquest_active_essence():
            raise ChapterError('Choose a light first. Nothing has been committed.')
        self.target_vessel = vessel
        self.error = ''

    def quick_reveal(self):
        if self.busy and self.offering:
            self._quick.set()

    async def commit(self, essence, vessel, refresh):
        if essence != self.state.masterquest_active_essence() or vessel != self.target_vessel:
            raise ChapterError('Your pairing changed. Review the displayed light and vessel before committing.')
        await self.offer(vessel, refresh)

    async def _pause(self, seconds):
        try:
            await asyncio.wait_for(self._quick.wait(), seconds)
        except TimeoutError:
            pass

    def _notify(self, refresh):
        try:
            refresh()
        except Exception:
            LOGGER.exception('Offering continues despite interrupted view callback.')

    def _settle(self, passed, original):
        s = self.state
        self.pending_verdict = passed
        if self._before is None:
            p = s.player
            brief = self.brief()
            self._before = {'name':p.name,'class':p.player_class,'level':p.level,'wins':p.wins,
                            'seconds':s.current_run_elapsed_seconds(),'next':brief['next'],'final':brief['final']}
        old = self._before
        def settle():
            original(passed)
            p = s.player
            return AscensionResult(self.session, passed, bool(passed and old['final']), old['name'], old['class'], old['next'],
                                   old['level'], old['wins'], old['seconds'], int(p.gold if p else s.shared_gold),
                                   len(p.inventory) if p else len(s.shared_inventory), len(s.labyrinth_roster_companions),
                                   int(s.ladder_stats.get(old['class'], {}).get('masterquest_attempts',0)))
        self.receipt = atomic_progress(s, settle)
        self.pending_verdict = None
        self.offering = None
        self.acknowledged = False
        s.dismiss_masterquest_result_popup()

    async def offer(self, vessel, refresh):
        s = self.state
        if not self.started or self.receipt or self.pending_verdict is not None:
            raise ChapterError('There is no active offering to submit.')
        if self.busy:
            return
        if self.offering:
            raise ChapterError('Continue the committed offering before making another choice.')
        if hero_key(s) != self.owner or s.game_tab != 'masterquest':
            raise ChapterError('The active climb changed. No offering was submitted.')
        essence = s.masterquest_active_essence()
        if vessel not in s.masterquest_container_order or vessel in s.masterquest_matched_containers or essence not in s.masterquest_solution:
            raise ChapterError('Select an unbound light, then an empty vessel.')
        self.sequence += 1
        self.last_essence, self.last_vessel = essence, vessel
        self.offering = Offering(essence, vessel, s.masterquest_solution[essence] == vessel)
        self._quick = asyncio.Event()
        await self._resolve(refresh)

    async def resume(self, refresh):
        if not self.offering or self.receipt or self.pending_verdict is not None:
            raise ChapterError('No interrupted offering is waiting.')
        if not self.busy:
            await self._resolve(refresh)

    async def _resolve(self, refresh):
        s, offering = self.state, self.offering
        self.busy, self.error = True, ''
        s.masterquest_resolving = True
        try:
            if not offering.applied:
                self.phase = 'judging'
                self._notify(refresh)
                await self._pause(2.7)
                if hero_key(s) != self.owner:
                    raise ChapterError('The active hero changed. Return to the original climb to continue.')
                if offering.correct:
                    s.masterquest_matched_essences.add(offering.essence)
                    s.masterquest_matched_containers.add(offering.vessel)
                    self.history.append((offering.essence, offering.vessel))
                offering.applied = True
                s.masterquest_selected_essence = ''
                s.clear_masterquest_drag()
            self.phase = 'matched' if offering.correct else 'rejected'
            self._notify(refresh)
            await self._pause(1.1)
            if hero_key(s) != self.owner:
                raise ChapterError('The active hero changed. Return to the original climb to continue.')
            if offering.correct and len(s.masterquest_matched_essences) < len(s.masterquest_essence_order):
                self.offering, self.target_vessel = None, ''
                self.phase = 'ritual'
            else:
                if offering.correct:
                    self.phase = 'unsealing'
                    self._notify(refresh)
                    await self._pause(1.4)
                    if hero_key(s) != self.owner:
                        raise ChapterError('The active hero changed. Return to the original climb to continue.')
                self._settle(offering.correct, s.finish_masterquest_attempt)
        except DesktopTransactionError as exc:
            self.error = str(exc)
        except asyncio.CancelledError:
            self.error = 'The reveal was interrupted. Continue your committed offering; its pairing is preserved.'
            raise
        except Exception:
            LOGGER.exception('Offering interrupted; committed pairing retained for recovery.')
            self.error = 'The reveal was interrupted. Continue the offering without paying again or changing its pairing.'
        finally:
            self.busy = False
            s.masterquest_resolving = False
            self._notify(refresh)

    def retry_settlement(self):
        if self.pending_verdict is None or self.receipt:
            raise ChapterError('No unsaved outcome is waiting.')
        self._settle(self.pending_verdict, self.state.finish_masterquest_attempt)
        self.error = ''

    def acknowledge(self):
        if not self.receipt:
            raise ChapterError('The rite has not resolved.')
        self.acknowledged = True
        self.state.dismiss_masterquest_result_popup()

    def signal(self):
        s = self.state
        phase = 'ritual' if self.started else 'threshold'
        if self.busy:
            phase = self.phase
        elif self.offering:
            phase = 'interrupted'
        elif self.target_vessel and s.masterquest_active_essence():
            phase = 'ready'
        if self.pending_verdict is not None:
            phase = 'save-error'
        if self.receipt:
            phase = 'final' if self.receipt.final else 'success' if self.receipt.passed else 'failure'
        return {'key':self.session,'step':self.sequence,'phase':phase,'matched':len(self.history),
                'essence':self.last_essence,'vessel':self.last_vessel,
                'duration':2700 if phase == 'judging' else 1400 if phase == 'unsealing' else 1100,
                'reduced':bool(s.accessibility_reduce_motion or s.disable_last_drop_animation)}


def market_for(state, game):
    key = hero_key(state)
    old = getattr(state, '_desktop_market', None)
    if old is None or old[0] != key:
        state._desktop_market = key, Market(state, game)
    return state._desktop_market[1]


def ascension_for(state, game):
    old = getattr(state, '_desktop_ascension', None)
    if old is None or old.owner != hero_key(state) or (old.receipt and old.acknowledged):
        state._desktop_ascension = Ascension(state, game)
    return state._desktop_ascension
