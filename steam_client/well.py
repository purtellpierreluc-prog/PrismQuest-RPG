"""A deliberate offering; atomic entry and retryable, non-rerolling settlement."""

import asyncio
import copy
import logging
import uuid
from dataclasses import dataclass, is_dataclass, replace

from .chapters import fingerprint, hero_key

LOGGER = logging.getLogger(__name__)


class WellError(ValueError):
    pass


def _data_keys(state):
    return {key for key,value in vars(state).items() if not key.startswith('_desktop') and not callable(value)
            and (value is None or isinstance(value,(str,int,float,bool,dict,list,tuple,set)) or is_dataclass(value))}


def _snapshot(state):
    return copy.deepcopy({key:vars(state)[key] for key in _data_keys(state)})


def _restore(state, snapshot):
    restored = copy.deepcopy(snapshot)
    for key in _data_keys(state) | set(restored):
        if key in restored:
            vars(state)[key] = restored[key]
        else:
            vars(state).pop(key,None)


class DeferredSaves:
    def __init__(self,state):
        self.state = state
        self.originals = {key:(key in vars(state),vars(state).get(key),getattr(state,key)) for key in ('persist_to_disk','persist_runtime_session')}

    def __enter__(self):
        self.state.persist_to_disk = lambda *args,**kwargs:None
        self.state.persist_runtime_session = lambda *args,**kwargs:None
        return self

    def __exit__(self,*args):
        for key,(owned,value,_) in self.originals.items():
            if owned:
                vars(self.state)[key] = value
            else:
                vars(self.state).pop(key,None)

    def commit(self):
        self.originals['persist_to_disk'][2](force=True)

    def publish(self):
        try:
            self.originals['persist_runtime_session'][2]()
        except Exception:
            LOGGER.exception('Well result saved; transient UI session update failed.')


@dataclass(frozen=True)
class WellReceipt:
    key: str
    outcome: str
    tier: int
    item_type: str
    item: object = None
    owned_item: object = None
    reward_index: int = -1


class Well:
    def __init__(self,state,game):
        self.state,self.game,self.owner = state,game,hero_key(state)
        self.session = uuid.uuid4().hex
        self.sequence = 0
        self.selected = self.armed = self.offering = self.receipt = None
        self.search,self.tier,self.kind = '','All tiers','All types'
        self.message = ''
        self.busy = self.interrupted = False
        self._pending_post = self._pending_action = None
        self._reward_before = 0

    @property
    def pending(self):
        return self._pending_post is not None or self._pending_action is not None

    def owns(self,item):
        return self.state.player is not None and any(candidate is item for candidate in self.state.player.inventory)

    def _notify(self,refresh):
        try:
            refresh()
        except Exception:
            LOGGER.exception('Well state retained despite an interrupted view callback.')

    def select(self,item):
        if self.busy or self.pending or self.interrupted:
            raise WellError('Finish the current bargain before choosing another offering.')
        if not self.owns(item) or item.rarity != 'Common':
            raise WellError('Choose a Common item from your pack.')
        self.selected,self.armed,self.message = item,None,''

    def blocker(self):
        s = self.state
        if self.busy or s.fight_in_progress or self.pending or self.interrupted:
            return 'An encounter or unsaved outcome is still waiting.'
        if s.player is None or not s.player.is_alive():
            return 'Recover at the Inn before making this bargain.'
        if not self.owns(self.selected) or self.selected.rarity != 'Common':
            return 'Choose a Common pack item. Nothing is preselected.'
        if s.player.level < self.game.item_required_level(self.selected):
            return f'This offering requires level {self.game.item_required_level(self.selected)}.'
        if s.player.gold < 10:
            return 'The well requires 10 gold.'
        return ''

    def arm(self):
        if self.blocker():
            raise WellError(self.blocker())
        self.armed = self.selected,fingerprint(self.selected)

    def _prepare(self,item):
        s,g = self.state,self.game
        monster,xp = g.generate_well_monster(s.player.level)
        index = next(i for i,candidate in enumerate(s.player.inventory) if candidate is item)
        previous = copy.deepcopy(s.last_monster_snapshot) if s.last_fight_outcome == 'victory' else None
        s.player.inventory.pop(index)
        s.pending_well_sacrifice_item = copy.deepcopy(item)
        s.player.gold -= 10
        s.record_town_service_spend('well',10)
        s.current_well_monster_asset_index = s.well_monster_cycle_index % 5
        s.well_monster_cycle_index += 1
        s.current_encounter_type,s.current_monster,s.current_monster_xp = 'well',monster,xp
        s.last_monster_snapshot,s.last_fight_outcome = None,'idle'
        s.arena_flee_requested = False
        s.mana_regen_progress = s.life_regen_progress = 0.0
        s.player_damage_popup_text = s.monster_damage_popup_text = ''
        s.fight_in_progress,s.page_turn_previous_monster = True,previous
        s.screen,s.game_tab = 'game','arena'
        s.apply_arena_combat_log_default()
        s._set_arena_transition(f'{monster.monster_personal_name} rises from the dark below.','warning')
        s.add_log(f'You offer 10 gold and a Common Tier {g.item_required_level(item)} {g.saved_item_type_label(item)}. Something wicked answers.','warning')
        s.add_log(f'{monster.monster_type} | Armor {monster.physical_armor} | M.Res {monster.magic_resistance}','muted')
        s.sync_active_slot()

    async def commit(self,refresh):
        armed,self.armed = self.armed,None
        if not armed:
            raise WellError('Review the exact offering before committing.')
        if self.blocker():
            raise WellError(self.blocker())
        if self.selected is not armed[0] or fingerprint(self.selected) != armed[1] or hero_key(self.state) != self.owner:
            raise WellError('The offering changed. Review its current details again.')
        s = self.state
        before = _snapshot(s)
        try:
            with DeferredSaves(s) as saves:
                self._prepare(self.selected)
            saves.commit()
        except Exception as exc:
            _restore(s,before)
            LOGGER.exception('Well entry rolled back before durable payment.')
            raise WellError('The offering could not be saved. Your gold, item and town spending were restored. Review the offering again after checking storage.') from exc
        saves.publish()
        self.offering,self.selected = copy.deepcopy(armed[0]),None
        self.sequence += 1
        self._reward_before = int(s.last_well_reward_sequence)
        await self._battle(refresh)

    async def legacy_start(self,refresh):
        reference = self.state.selected_well_sacrifice_ref()
        if not reference:
            raise WellError('Choose a Common offering first.')
        self.select(reference[1])
        self.arm()
        await self.commit(refresh)

    async def _battle(self,refresh):
        s = self.state
        self.busy,self.interrupted,self.message = True,False,''
        try:
            s.fight_in_progress = True
            s.screen,s.game_tab = 'game','arena'
            self._notify(refresh)
            redraw = lambda *args,**kwargs:self._notify(refresh)
            await s._animate_monster_page_turn_async(redraw)
            s._set_arena_transition('')
            await s._run_arena_combat_async(redraw)
            if not self.pending and not s.fight_in_progress and (not self.receipt or self.receipt.key != self.key):
                self.receipt = self._make_receipt()
        except asyncio.CancelledError:
            self.interrupted = not self.pending
            if self.pending:
                self._hold()
            else:
                self.message = 'The encounter was interrupted. Continue the same foe without paying again.'
            s.fight_in_progress = False
            if s.player is not None:
                s.screen,s.game_tab = 'game','well'
            raise
        except Exception:
            LOGGER.exception('Committed Well encounter interrupted; no payment or offering was refunded.')
            self.interrupted = not self.pending and (not self.receipt or self.receipt.key != self.key)
            if self.pending:
                self._hold()
            else:
                self.message = 'The encounter was interrupted. Continue the same foe; no new offering or payment is needed.'
            s.fight_in_progress = False
            if s.player is not None:
                s.screen,s.game_tab = 'game','well'
        finally:
            self.busy = False
            self._notify(refresh)

    async def resume(self,refresh):
        if not self.interrupted or self.state.current_monster is None:
            raise WellError('There is no interrupted encounter to continue.')
        await self._battle(refresh)

    @property
    def key(self):
        return f'{self.session}:{self.sequence}'

    def _make_receipt(self):
        s,g = self.state,self.game
        tier = g.item_required_level(self.offering) if self.offering else int(s.last_well_reward_tier)
        kind = g.saved_item_type_label(self.offering) if self.offering else str(s.last_well_reward_type)
        outcome = 'defeat' if s.player is None or s.last_fight_outcome == 'defeat' else 'fled' if s.last_fight_outcome in {'fled','flee'} else 'miss'
        if s.last_fight_outcome == 'victory' and int(s.last_well_reward_sequence)>self._reward_before and s.last_well_reward_outcome == 'item':
            index = len(s.player.inventory)-1
            item = s.player.inventory[index]
            if item.to_dict() != s.last_well_reward_item.to_dict():
                raise WellError('The returned item could not be identified safely.')
            return WellReceipt(self.key,'item',tier,kind,copy.deepcopy(item),item,index)
        return WellReceipt(self.key,outcome,tier,kind)

    def _hold(self):
        self.state.fight_in_progress = False
        if self.state.player is not None:
            self.state.screen,self.state.game_tab = 'game','well'
        self.message = 'The outcome is waiting to be saved. Retry it here; do not start another bargain. Payment will not be refunded or charged twice.'

    async def settle(self,action,refresh):
        s = self.state
        before = _snapshot(s)
        self._pending_action = action
        try:
            with DeferredSaves(s) as saves:
                s._desktop_well_settling = True
                await action(lambda *args,**kwargs:None)
                receipt = self._make_receipt()
                post = _snapshot(s)
        except BaseException:
            _restore(s,before)
            self._hold()
            LOGGER.exception('Well settlement interrupted before commit; staged changes restored.')
            raise
        finally:
            s._desktop_well_settling = False
        self._pending_action = None
        self._pending_post = post,receipt
        try:
            saves.commit()
        except Exception:
            LOGGER.exception('Well outcome save failed; the rolled outcome is retained for retry.')
            _restore(s,before)
            self._hold()
        else:
            self.receipt,self._pending_post,self.message = receipt,None,''
            saves.publish()
        self._notify(refresh)

    async def retry_settlement(self,refresh):
        if self._pending_post is not None:
            s = self.state
            before = _snapshot(s)
            post,receipt = self._pending_post
            try:
                _restore(s,post)
                if receipt.outcome == 'item':
                    receipt = replace(receipt,owned_item=s.player.inventory[receipt.reward_index])
                s.persist_to_disk(force=True)
            except Exception as exc:
                _restore(s,before)
                LOGGER.exception('Retained Well outcome still could not be saved.')
                raise WellError('The same rolled outcome is retained. Check storage and retry.') from exc
            self.receipt,self._pending_post,self.message = receipt,None,''
            try:
                s.persist_runtime_session()
            except Exception:
                LOGGER.exception('Well retry committed; UI session update failed.')
            self._notify(refresh)
        elif self._pending_action is not None:
            await self.settle(self._pending_action,refresh)
        else:
            raise WellError('No unsaved outcome is waiting.')


def well_for(state,game):
    old = getattr(state,'_desktop_well',None)
    if old is None or old.owner != hero_key(state):
        state._desktop_well = Well(state,game)
    return state._desktop_well
