"""Versioned, lossless validation at the local-save boundary."""

import math

from .town_data import validate_town

CURRENT_SAVE_VERSION = 3


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
    for field in ('vault_items',) if player is not None else ('vault_items','carryover_inventory'):
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
    for index,listing in enumerate(slot.get('town_services',{}).get('listings',[])):
        if listing.get('status') == 'active':
            yield f'town.listings[{index}].item',listing['item']


def validate_slots(slots):
    if not isinstance(slots, list) or len(slots) != 3 or not all(isinstance(slot, dict) for slot in slots):
        raise ValueError('Save document must contain three chronicle slots.')
    for slot in slots:
        validate_town(slot.get('town_services',{}),validate_item)
        # While a hero lives this is a next-run mirror, not a second owned pack.
        if slot.get('player') is not None:
            carryover = slot.get('carryover_inventory',[])
            if not isinstance(carryover,list):
                raise TypeError('carryover_inventory must be a list.')
            for item in carryover:
                validate_item(item,'carryover snapshot')
        spending = slot.get('town_service_spend', {})
        if not isinstance(spending, dict) or any(not isinstance(k, str) or not 0 < len(k) <= 48 or type(v) is not int or v < 0 for k,v in spending.items()):
            raise ValueError('Town service spending must contain nonnegative integer totals.')
        player = slot.get('player')
        if isinstance(player, dict):
            gold = player.get('gold', 0)
            if not isinstance(gold, (int, float)) or not math.isfinite(gold) or gold < 0:
                raise ValueError('Player gold must be finite and nonnegative.')
        for location, item in owned_items(slot):
            validate_item(item, location)
    listing_ids,guild_ids,codes = set(),{},set()
    for index,slot in enumerate(slots):
        town = slot.get('town_services',{})
        for row in town.get('listings',[]):
            if row['id'] in listing_ids:
                raise ValueError('A listing identity is shared by multiple chronicles.')
            listing_ids.add(row['id'])
        for guild in town.get('charters',[]):
            if guild['id'] in guild_ids or guild['code'] in codes or guild['founder'] != index:
                raise ValueError('Guild charter ownership or identity is inconsistent.')
            guild_ids[guild['id']] = index
            codes.add(guild['code'])
    for slot in slots:
        identity = slot.get('town_services',{}).get('guild_id','')
        if identity and identity not in guild_ids:
            raise ValueError('Guild membership refers to a missing local charter.')
    return slots
