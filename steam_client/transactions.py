"""Commit synchronous desktop economy actions once, or restore their prior state."""

import copy
import functools
import logging

LOGGER = logging.getLogger(__name__)
STATE_FIELDS = (
    'player', 'slots', 'saved_item_sets', 'saved_set_collapsed', 'vault_items', 'vault_capacity',
    'shared_inventory', 'shared_gold', 'shared_proficiency_levels', 'shared_proficiency_progress',
    'labyrinth_roster_companions', 'labyrinth_session_row', 'labyrinth_member_rows', 'labyrinth_vote_rows',
    'labyrinth_last_snapshot_hash', 'labyrinth_snapshot_revision', 'labyrinth_last_self_snapshot_key',
    'labyrinth_last_slot_sync_at', 'labyrinth_status', 'labyrinth_selected_roster_item_keys',
    'town_coffers_total', 'town_coffers_by_service', 'town_coffers_source', 'local_town_service_spend',
    'town_coffers_sync_ok', 'town_coffers_sync_message', 'marketplace_offers',
    'log', '_last_local_slots_hash', '_last_runtime_session_hash', 'selected_inventory_key',
    'hovered_inventory_key', 'inventory_view', 'transmute_choice_one', 'transmute_choice_two',
    'transmute_last_result_item', 'transmute_reveal_lines', 'transmute_reveal_active',
)
ITEM_ACTIONS = (
    'equip_item', 'sell_item', 'sell_inventory_items', 'delete_inventory_item', 'delete_saved_item', 'unequip_slot',
    'save_selected_item_to_set', 'retrieve_saved_item_to_inventory', 'equip_saved_item',
    'buy_vault_slots', 'store_vault_item', 'withdraw_vault_item', 'transmute_selected',
    'buy_marketplace_offer', 'labyrinth_buy_roster_companion', 'labyrinth_rename_roster_companion',
    'labyrinth_set_roster_companion_item', 'labyrinth_clear_roster_companion_item',
    'allocate', 'allocate_multiple',
)


class DesktopTransactionError(RuntimeError):
    pass


def install_item_transactions(state_type, enabled):
    for name in ITEM_ACTIONS:
        original = getattr(state_type, name)
        if getattr(original, '_desktop_transaction', False):
            continue

        @functools.wraps(original)
        def action(state, *args, _original=original, **kwargs):
            if not enabled() or getattr(state, '_desktop_transaction_active', False):
                return _original(state, *args, **kwargs)
            # These actions are synchronous: no UI callback can interleave a
            # second mutation between staging ownership and the atomic disk write.
            snapshot = copy.deepcopy({key: state.__dict__[key] for key in STATE_FIELDS if key in state.__dict__})
            prior_override = state.__dict__.get('persist_to_disk')
            had_override = 'persist_to_disk' in state.__dict__
            persist = state.persist_to_disk
            pending = False
            force = False

            def defer(*_args, **kw):
                nonlocal pending, force
                pending = True
                force = force or bool(kw.get('force', False))

            state._desktop_transaction_active = True
            state.persist_to_disk = defer
            try:
                result = _original(state, *args, **kwargs)
                if pending:
                    persist(force=force)
                return result
            except Exception as exc:
                for key in STATE_FIELDS:
                    if key in snapshot:
                        state.__dict__[key] = snapshot[key]
                    else:
                        state.__dict__.pop(key, None)
                LOGGER.exception('Desktop item action %s rolled back before commit.', _original.__name__)
                raise DesktopTransactionError('The item action could not be saved and was cancelled. Your previous items and gold were restored. Check storage space; if the save changed externally, close and reopen the game.') from exc
            finally:
                if had_override:
                    state.persist_to_disk = prior_override
                else:
                    state.__dict__.pop('persist_to_disk', None)
                state._desktop_transaction_active = False

        action._desktop_transaction = True
        setattr(state_type, name, action)
