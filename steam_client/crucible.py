"""Explicit offering selection and read-only forecasts around the existing ritual."""

import copy
import json
import uuid
from collections import defaultdict
from dataclasses import dataclass, field


class CrucibleError(ValueError):
    pass


@dataclass(frozen=True)
class RarityChance:
    rarity: str
    percent: int


@dataclass(frozen=True)
class Quote:
    blocker: str
    cost: int = 0
    tier: int = 0
    subtype: str = ''
    outcomes: tuple = ()


@dataclass(frozen=True)
class RitualReceipt:
    serial: int
    item: object = field(repr=False, compare=False)
    owned_item: object = field(repr=False, compare=False)
    first: object = field(repr=False, compare=False)
    second: object = field(repr=False, compare=False)
    cost: int = 0
    rarity_delta: int = 0


class Crucible:
    def __init__(self, state, game):
        self.state, self.game = state, game
        self.first = self.second = None
        self.target = 'form'
        self.armed = None
        self.receipt = None
        self.sequence = 0
        self.session = uuid.uuid4().hex
        self.detail = 'forecast'
        self.tier = 'All tiers'
        self.rarity = 'All rarities'
        self.search = ''
        self.message = ''
        self.error = False

    def owns(self, item):
        return item is not None and any(candidate is item for candidate in self.state.player.inventory)

    def set_target(self, target):
        if target not in ('form', 'fuel'):
            raise CrucibleError('Choose Form or Sacrifice.')
        if target == 'fuel' and not self.owns(self.first):
            raise CrucibleError('Choose the form first. It determines the result type and tier.')
        self.target, self.armed = target, None

    def clear(self, target=None):
        if target in (None, 'form'):
            self.first = self.second = None
            self.target = 'form'
        else:
            self.second = None
            self.target = 'fuel' if self.owns(self.first) else 'form'
        self.armed = None
        self.detail = 'forecast'

    def choose(self, item):
        if not self.owns(item):
            raise CrucibleError('That item is no longer in your pack. Choose a current offering.')
        if not self.state.transmute_item_is_eligible(item):
            raise CrucibleError('The crucible accepts Fine or better, not Common items.')
        if self.target == 'form':
            self.first = item
            if self.second is item or (self.second and not self.state.transmute_items_match(item, self.second)):
                self.second = None
            self.target = 'fuel'
        else:
            if not self.owns(self.first):
                raise CrucibleError('Choose a form first.')
            if item is self.first:
                raise CrucibleError('The sacrifice must be a different item.')
            if not self.state.transmute_items_match(self.first, item):
                raise CrucibleError(f'The sacrifice must also be Tier {self.game.item_required_level(self.first)}.')
            self.second = item
        self.armed, self.detail, self.message = None, 'forecast', ''

    def quote(self):
        if not self.owns(self.first):
            return Quote('Choose a form. Its item type and tier will survive.')
        if not self.owns(self.second):
            return Quote('Add a different Fine-or-better item of the same tier.', tier=self.game.item_required_level(self.first), subtype=self.first.subtype)
        if self.first is self.second or not all(self.state.transmute_item_is_eligible(item) for item in (self.first, self.second)) or not self.state.transmute_items_match(self.first, self.second):
            return Quote('Choose two different Fine-or-better offerings of the same tier.')
        order = self.game.RARITY_ORDER
        low, high = sorted((self.first.rarity, self.second.rarity), key=order.index)
        chances = defaultdict(int)
        for rarity, chance in [(self.game.shift_rarity(low, 1), 35), (self.game.normalize_loot_rarity(high), 50), (self.game.shift_rarity(high, -1), 15)]:
            chances[rarity] += chance
        cost = self.state.transmute_gold_cost(self.first, self.second)
        return Quote('Not enough gold. Your offerings will not be consumed.' if self.state.player.gold < cost else '',
                     cost, self.game.item_required_level(self.first), self.first.subtype,
                     tuple(RarityChance(rarity, chances[rarity]) for rarity in sorted(chances, key=order.index, reverse=True)))

    @staticmethod
    def fingerprint(item):
        return json.dumps(item.to_dict(), sort_keys=True, separators=(',', ':'))

    def arm(self):
        quote = self.quote()
        if quote.blocker:
            raise CrucibleError(quote.blocker)
        self.armed = (self.first, self.second, self.fingerprint(self.first), self.fingerprint(self.second), quote.cost)
        return quote

    def commit(self):
        armed, self.armed = self.armed, None
        if not armed:
            raise CrucibleError('Review and confirm the two offerings first.')
        quote = self.quote()
        if quote.blocker:
            raise CrucibleError(quote.blocker)
        if self.first is not armed[0] or self.second is not armed[1] or self.fingerprint(self.first) != armed[2] or self.fingerprint(self.second) != armed[3] or quote.cost != armed[4]:
            raise CrucibleError('An offering changed. Review the items and confirm again.')
        first, second = copy.deepcopy(self.first), copy.deepcopy(self.second)
        labels = self.state.transmute_item_map()
        one = next((key for key, ref in labels.items() if ref[2] is self.first), None)
        two = next((key for key, ref in labels.items() if ref[2] is self.second), None)
        if one is None or two is None:
            raise CrucibleError('An offering moved. Nothing was consumed.')
        old_filters = self.state.transmute_filter_settings()
        self.state.transmute_tier_filter, self.state.transmute_rarity_filter = 'All tiers', 'All rarities'
        self.state.transmute_choice_one, self.state.transmute_choice_two = one, two
        try:
            # Keep the original transaction, random roll, fees and persistence.
            # Its UI-era default selection cannot substitute a filtered item.
            self.state.transmute_selected()
        finally:
            self.state.transmute_tier_filter, self.state.transmute_rarity_filter = old_filters
        result = self.state.transmute_last_result_item
        if result is None:
            raise CrucibleError(self.state.transmute_message or 'The ritual did not complete.')
        self.sequence += 1
        self.receipt = RitualReceipt(self.sequence, copy.deepcopy(result), result, first, second, quote.cost,
                                     self.game.RARITY_ORDER.index(result.rarity) - self.game.RARITY_ORDER.index(first.rarity))
        self.state.transmute_reveal_active = False
        self.state.transmute_reveal_stage = 5
        self.state.transmute_reveal_visible_count = len(self.state.transmute_reveal_lines)
        self.clear()
        self.detail = 'result'
        self.message, self.error = '', False
        return self.receipt


def workbench_for(state, game):
    key = (state.active_slot_index, state.player.name, state.player.player_class, getattr(state, 'current_run_start_wall_time', 0))
    previous = getattr(state, '_desktop_crucible', None)
    if previous is None or previous[0] != key:
        state._desktop_crucible = key, Crucible(state, game)
    return state._desktop_crucible[1]
