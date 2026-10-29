"""Read-only experience models. No item ownership or combat rules live here."""

import copy
import functools
import logging
from dataclasses import dataclass, field, replace

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Journey:
    title: str
    detail: str
    action: str
    destination: str
    milestone: str
    progress: float


def journey_for(player, *, quest_available=False, quest_blocker='', lab_active=False):
    level = max(1, int(player.level))
    if player.hp < player.max_hp * .30:
        return Journey('Live to climb again', 'Your health is low. The Inn restores your footing before the next fight.',
                       'Recover at the Inn', 'inn', 'RECOVERY', level / 60)
    if player.unspent_stat_points > 0:
        return Journey('Turn experience into power', f'{player.unspent_stat_points} unspent points are waiting. Allocate them to shape your build.',
                       'Shape Your Build', 'stats', 'BUILD DECISION', min(1, level / 60))
    if quest_available:
        return Journey('The prism is within reach', 'Your next class is earned through Prismatic Quest. Prepare your gear before taking the risk.',
                       'Approach the Prism', 'masterquest', 'ASCENSION READY', 1)
    if lab_active:
        return Journey('Your expedition is waiting', 'Return to your party and continue the current Labyrinth without abandoning its progress.',
                       'Continue Expedition', 'labyrinth', 'EXPEDITION IN PROGRESS', min(1, level / 60))
    if level >= 60:
        return Journey('Prepare for ascension', quest_blocker or 'Refine your equipment, then challenge Prismatic Quest.',
                       'Review Your Equipment', 'inventory', 'PRISMATIC QUEST', 1)
    milestone = 45 if level < 45 else 60
    return Journey('Build a legend, one victory at a time' if level < 45 else 'The Labyrinth is open',
                   f'Reach level {milestone}. Fight for experience, inspect new drops, and replace gear as higher tiers become available.'
                   if level < 45 else 'Keep climbing in the Arena, or lead companions into the Labyrinth for a different kind of ascent.',
                   'Enter the Arena' if level < 45 else 'Explore the Labyrinth',
                   'arena' if level < 45 else 'labyrinth', f'NEXT MILESTONE / LEVEL {milestone}', min(1, level / milestone))


@dataclass(frozen=True)
class BattleStart:
    serial: int
    slot: object
    level: int
    xp: int
    gold: int
    inventory: tuple = field(repr=False)


@dataclass(frozen=True)
class BattleResult:
    serial: int
    slot: object
    outcome: str
    xp: int
    gold: int
    levels: int
    monster: str
    item: object = field(default=None, repr=False, compare=False)
    hero_key: tuple = ()


def begin_battle(state):
    p = state.player
    state._experience_result = None
    serial = int(getattr(state, '_experience_serial', 0)) + 1
    state._experience_serial = serial
    state._experience_start = BattleStart(serial, state.active_slot_index, p.level, p.xp, p.gold, tuple(p.inventory))


def finish_battle(state, xp_threshold):
    start = getattr(state, '_experience_start', None)
    p = state.player
    if not start or not p or start.slot != state.active_slot_index:
        return
    if state.fight_in_progress or state.last_fight_outcome not in {'victory', 'defeat', 'fled'}:
        return
    previous = getattr(state, '_experience_result', None)
    if previous and previous.serial == start.serial:
        return
    levels = max(0, p.level - start.level)
    xp = p.xp - start.xp + sum(xp_threshold(level) for level in range(start.level, p.level))
    # Object identity is intentional. Equal rolls are distinct legal items.
    old = {id(item) for item in start.inventory}
    new_items = [item for item in p.inventory if id(item) not in old]
    monster = getattr(state, 'last_monster_snapshot', None)
    state._experience_result = BattleResult(start.serial, start.slot, state.last_fight_outcome, xp,
                                             p.gold - start.gold, levels,
                                             str(getattr(monster, 'monster_type', 'Challenger')),
                                             new_items[-1] if new_items else None,
                                             (p.name, p.player_class, p.wins, p.losses))
    state._experience_start = None


def install_battle_feedback(state_type, *, enabled, xp_threshold):
    """Observe existing lifecycle callbacks; never change their result or timing."""
    if getattr(state_type._run_arena_combat_async, '_experience_feedback', False):
        return
    run = state_type._run_arena_combat_async
    finish = state_type._finish_arena_fight_async

    @functools.wraps(run)
    async def observed_run(state, refresh):
        if enabled() and state.player is not None:
            begin_battle(state)
        return await run(state, refresh)

    @functools.wraps(finish)
    async def observed_finish(state, refresh):
        if enabled() and state.player is not None and getattr(state, '_experience_start', None):
            # The simulator replaces the combatant with a deep copy before payout.
            # Take ownership identities here, before that payout appends its drop.
            state._experience_start = replace(state._experience_start, inventory=tuple(state.player.inventory))
        def present():
            if enabled():
                try:
                    finish_battle(state, xp_threshold)
                except Exception:
                    LOGGER.exception('Battle receipt unavailable; gameplay is unaffected.')
            return refresh()
        return await finish(state, present)

    observed_run._experience_feedback = True
    state_type._run_arena_combat_async = observed_run
    state_type._finish_arena_fight_async = observed_finish


def current_result(state):
    result = getattr(state, '_experience_result', None)
    p = state.player
    return result if result and p and result.slot == state.active_slot_index and result.hero_key == (p.name, p.player_class, p.wins, p.losses) else None


def owned_item_index(player, item):
    return next((index for index, candidate in enumerate(player.inventory) if candidate is item), None)


@dataclass(frozen=True)
class StatChange:
    label: str
    before: float
    after: float
    percent: bool = False

    @property
    def delta(self):
        return self.after - self.before

    def formatted(self, value):
        if self.percent:
            return f'{value * 100:.1f}%'
        return f'{value:,.1f}' if 'average' in self.label else f'{value:,.0f}'


def equipment_changes(player, item, can_equip):
    allowed, reason = can_equip(player, item)
    if not allowed:
        return reason, []
    # Only clone the combatant; don't walk a full inventory on each selection.
    preview = copy.copy(player)
    preview.equipped = dict(player.equipped)
    preview.equipped[item.slot] = item
    preview.recalculate_stats()
    stats = [('Weapon average', 'weapon_attack_min', 'weapon_attack_max'),
             ('Spell average', 'spell_attack_min', 'spell_attack_max')]
    changes = [StatChange(label, (getattr(player, low) + getattr(player, high)) / 2,
                          (getattr(preview, low) + getattr(preview, high)) / 2)
               for label, low, high in stats]
    for label, key, percent in [('Max health', 'max_hp', False), ('Max mana', 'max_mana', False),
                                 ('Armor', 'physical_armor', False), ('Magic resist', 'magic_resistance', False),
                                 ('Critical chance', 'crit_chance', True), ('Evasion', 'evasion', True),
                                 ('Magic find', 'magic_find', True), ('Life steal', 'lifesteal', True)]:
        changes.append(StatChange(label, getattr(player, key), getattr(preview, key), percent))
    return '', [change for change in changes if abs(change.delta) > .00001]


def labyrinth_progress(row):
    size = max(1, min(20, int(row.get('grid_size', 7) or 7)))
    tiles = row.get('tile_states', {})
    resolved = sum(bool(tile.get('resolved')) for tile in tiles.values() if isinstance(tile, dict)) if isinstance(tiles, dict) else 0
    return min(size * size, resolved), size * size
