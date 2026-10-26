"""Versioned, lossless validation at the local-save boundary."""

import math

CURRENT_SAVE_VERSION = 2


def validate_item(item, location):
    if not isinstance(item, dict):
        raise TypeError(f'{location} must be an item object.')
    if not isinstance(item.get('name'), str) or item.get('slot') not in {'weapon', 'armor', 'charm'}:
        raise ValueError(f'{location} has invalid identity/type fields.')
    level = item.get('level')
    if not isinstance(level, int) or isinstance(level, bool) or level < 1:
        raise ValueError(f'{location} has an invalid tier.')
    for field in ('base_stats', 'affix_stats'):
        stats = item.get(field, {})
        if not isinstance(stats, dict) or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in stats.values()):
            raise ValueError(f'{location}.{field} contains invalid stats.')


def owned_items(slot):
    """Enumerate ownership, not display snapshots or last-loot previews.

    Equal item stats are legal. Without persistent item IDs, value equality is
    never evidence that an item should be removed or deduplicated.
    """
    player = slot.get('player')
    if player is not None and not isinstance(player, dict):
        raise ValueError('player must be an object or null.')
    owner = player if isinstance(player, dict) else {}
    for field in ('inventory',):
        values = owner.get(field, [])
        if not isinstance(values, list):
            raise TypeError(f'player.{field} must be a list.')
        for index, item in enumerate(values):
            yield f'player.{field}[{index}]', item
    equipped = owner.get('equipped', {})
    if not isinstance(equipped, dict):
        raise TypeError('player.equipped must be an object.')
    for key, item in equipped.items():
        if item is not None:
            yield f'player.equipped.{key}', item
    for field in ('vault_items', 'carryover_inventory'):
        values = slot.get(field, [])
        if not isinstance(values, list):
            raise TypeError(f'{field} must be a list.')
        for index, item in enumerate(values):
            yield f'{field}[{index}]', item
    saved = slot.get('saved_item_sets', {})
    if not isinstance(saved, dict):
        raise TypeError('saved_item_sets must be an object.')
    for category, values in saved.items():
        if not isinstance(values, dict):
            raise TypeError('Saved-set categories must be objects.')
        for tier, item in values.items():
            if item is not None:
                yield f'saved_item_sets.{category}.{tier}', item
    roster = slot.get('labyrinth_roster_companions', [])
    if not isinstance(roster, list):
        raise TypeError('Companion roster must be a list.')
    for index, entry in enumerate(roster):
        if not isinstance(entry, dict) or not isinstance(entry.get('equipped', {}), dict):
            raise TypeError('Companion equipment must be an object.')
        for key, item in entry.get('equipped', {}).items():
            if item is not None:
                yield f'roster[{index}].{key}', item


def validate_slots(slots):
    if not isinstance(slots, list) or len(slots) != 3 or not all(isinstance(slot, dict) for slot in slots):
        raise ValueError('Save document must contain three chronicle slots.')
    for slot in slots:
        player = slot.get('player')
        if isinstance(player, dict):
            gold = player.get('gold', 0)
            if not isinstance(gold, (int, float)) or not math.isfinite(gold) or gold < 0:
                raise ValueError('Player gold must be finite and nonnegative.')
        for location, item in owned_items(slot):
            validate_item(item, location)
    return slots
