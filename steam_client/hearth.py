"""Read-only room forecasts and an honest receipt over the existing Inn rules."""

import uuid
from dataclasses import dataclass

from .chapters import hero_key


class HearthError(ValueError):
    pass


@dataclass(frozen=True)
class RestForecast:
    cost: int
    hp_before: int
    hp_after: int
    mana_before: int
    mana_after: int
    chain: int

    @property
    def useful(self):
        return self.hp_after > self.hp_before or self.mana_after > self.mana_before or self.chain > 0


@dataclass(frozen=True)
class RestReceipt:
    key: str
    cost: int
    health: int
    mana: int
    chain: int


def forecast(state,game):
    p = state.player
    return RestForecast(game.inn_rest_cost(p.player_class),p.hp,min(p.max_hp,p.hp+max(10,int(p.max_hp*.35))),
                        p.mana,min(p.max_mana,p.mana+max(4,int(max(1,p.max_mana)*.35))),int(state.monster_chain_combo))


class Hearth:
    def __init__(self,state,game):
        self.state,self.game,self.owner = state,game,hero_key(state)
        self.receipt = self.reviewed_chain = None
        self.message = ''

    def blocker(self):
        if self.state.player is None or self.state.fight_in_progress or self.state.current_monster is not None:
            return 'Finish your encounter before taking a room.'
        view = forecast(self.state,self.game)
        if self.state.player.gold < view.cost:
            return f'A room costs {view.cost:,} gold. You do not have enough yet.'
        if not view.useful:
            return 'Fully recovered. Your next road is waiting.'
        return ''

    def rest(self):
        if self.blocker():
            raise HearthError(self.blocker())
        if hero_key(self.state) != self.owner:
            raise HearthError('Your hero changed. Reopen the Inn before resting.')
        before = forecast(self.state,self.game)
        if before.chain and self.reviewed_chain != before.chain:
            self.reviewed_chain = before.chain
            return None
        self.reviewed_chain = None
        self.state.inn_rest()
        p = self.state.player
        self.receipt = RestReceipt(uuid.uuid4().hex,before.cost,p.hp-before.hp_before,p.mana-before.mana_before,before.chain)
        self.message = ''
        return self.receipt


def hearth_for(state,game):
    current = getattr(state,'_desktop_hearth',None)
    if current is None or current.owner != hero_key(state):
        state._desktop_hearth = Hearth(state,game)
    return state._desktop_hearth
