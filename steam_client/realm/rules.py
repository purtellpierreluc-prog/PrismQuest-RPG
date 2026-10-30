"""Headless adapter for the existing, trusted game rules.

The legacy source also contains UI startup and desktop persistence. Remove those
entry points before loading a private rules instance; never execute downloaded code.
"""

import ast
import random
import secrets
import sys
import types
from dataclasses import asdict
from pathlib import Path


class Rules:
    def __init__(self, resources):
        source = Path(resources) / 'PrismQuest_RPG_v1.01.py'
        tree = ast.parse(source.read_text(encoding='utf-8-sig'))
        kept = []
        for node in tree.body:
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                name = ast.unparse(node.value.func)
                if name.startswith(('ui.', 'app.')) or name in {'install_item_transactions', 'install_battle_feedback'} or (name == 'os.makedirs' and 'GENERATED_STATIC_DIR' in ast.unparse(node)):
                    continue
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                node.decorator_list = [d for d in node.decorator_list if not ast.unparse(d).startswith(('ui.', 'app.'))]
                if node.name == '_image_path_to_data_uri':
                    node.body = [ast.Return(ast.Constant(''))]
            if isinstance(node, ast.Try) and 'os.chdir' in ast.unparse(node):
                continue
            if isinstance(node, ast.Assign):
                names = [ast.unparse(t) for t in node.targets]
                if 'DESKTOP_MODE' in names:
                    node.value = ast.Constant(False)
                if any(name in names for name in ('SUPABASE_URL', 'SUPABASE_PUBLISHABLE_KEY')):
                    node.value = ast.Constant('')
            kept.append(node)
        tree.body = kept
        module = types.ModuleType('prismquest_realm_rules_' + secrets.token_hex(6))
        module.__file__ = str(source)
        sys.modules[module.__name__] = module
        try:
            exec(compile(ast.fix_missing_locations(tree), str(source), 'exec'), module.__dict__)  # noqa: S102 - trusted packaged source only
        except BaseException:
            sys.modules.pop(module.__name__, None)
            raise
        # A private RNG keeps online commands from perturbing solo combat rolls.
        module.random = random.Random(secrets.randbits(256))
        module._labyrinth_local_member_id = lambda state: state.realm_user_id
        module.SUPABASE_ENABLED = False
        module.load_persisted_slots = lambda: [module.build_default_slot_payload() for _ in range(3)]
        # Headless state must not even read/migrate NiceGUI browser storage.
        # Disable these on the isolated class before its constructor runs.
        for name in ('restore_ui_preferences', 'restore_auth_session', 'restore_runtime_session',
                     'persist_runtime_session', 'persist_to_disk', 'sync_active_slot'):
            setattr(module.SessionState, name, lambda self, *args, **kwargs: None)
        module.SessionState._stored_runtime_session = lambda self: {}
        module.SessionState.is_authenticated = lambda self: False
        module._ensure_disconnect_logger = lambda: None
        self.game = module

    def create(self, name, player_class):
        if player_class not in ('Black Guard', 'Shadow Mage', 'Shadow Warrior', 'Night Angel'):
            raise ValueError('Choose a feeder class.')
        player = self.game.create_player(player_class)
        player.name = name
        return player

    def state(self, user_id, player, checkpoint=None):
        g = self.game
        state = g.SessionState()
        state.realm_user_id = user_id
        state.player = player
        state.slots = [g.build_default_slot_payload() for _ in range(3)]
        state.active_slot_index = 0
        state.screen = 'game'
        state.game_tab = 'labyrinth'
        state.supabase = None
        state.guided_intro_stage = g.GUIDED_INTRO_COMPLETE
        state.sync_active_slot = lambda *args, **kwargs: None
        state.persist_to_disk = lambda *args, **kwargs: None
        state.persist_runtime_session = lambda *args, **kwargs: None
        state.labyrinth_is_local = True
        if checkpoint and not g.restore_desktop_labyrinth(state, checkpoint):
            raise ValueError('The saved expedition could not be restored; no progress was changed.')
        return state

    def member(self, user_id, player):
        state = self.state(user_id, player)
        return self.game._labyrinth_normalize_member_row(self.game._labyrinth_member_payload(state))

    def arena(self, player):
        g = self.game
        if player.hp <= 0:
            raise ValueError('Recover at the realm Inn before fighting.')
        monster, xp = g.generate_monster(player.level, forced_level=player.level, player_class=player.player_class)
        timeline = g.build_combat_timeline(player, monster)
        gold = 0
        if player.hp > 0 and monster.hp <= 0:
            g.gain_xp(player, xp)
            gold = max(1, player.level * 2)
            player.gold += gold
            if g.random.random() < .5:
                player.inventory.append(g.generate_item_drop(monster.level, player.player_class, player.magic_find))
        return {'monster': asdict(monster), 'log': [row[0].text for row in timeline][-12:], 'gold': gold}

    def advance(self, party, players, actor, operation, args):
        g = self.game
        checkpoint = party.get('checkpoint')
        leader = party['leader']
        if not checkpoint:
            state = self.state(leader, players[leader])
            if not state.create_labyrinth_solo_session():
                raise ValueError(state.labyrinth_status)
            state.labyrinth_member_rows = [self.member(uid, players[uid]) for uid in party['members']]
            if not state.labyrinth_start_floor():
                raise ValueError(state.labyrinth_status)
        else:
            state = self.state(actor, players[actor], checkpoint)
            if operation == 'move':
                ok = state.labyrinth_move_party(args.get('direction', ''))
            elif operation == 'ability':
                ok = state.labyrinth_activate_ability(actor)
            elif operation == 'tank':
                ok = state.labyrinth_set_tank_role(actor, bool(args.get('enabled')))
            elif operation == 'vote':
                ok = state.vote_labyrinth_reward(int(args.get('choice', -1)))
            else:
                ok = operation == 'refresh'
            if not ok:
                raise ValueError(state.labyrinth_status or 'That expedition action is unavailable.')
        # One server resolves combat; clients receive a compact, shared result.
        for _step in range(220):
            if state.labyrinth_session_row.get('status') not in ('encounter', 'boss'):
                break
            if not state.run_labyrinth_encounter(ignore_timing=True):
                raise ValueError('The encounter could not advance; the command was rolled back.')
        else:
            raise ValueError('Encounter safety limit reached; the command was rolled back.')
        checkpoint = g.capture_desktop_labyrinth(state)
        session = checkpoint['session']
        if session.get('status') == 'reward':
            deadline = g._labyrinth_parse_iso_timestamp(session.get('pending_encounter', {}).get('reward_vote_started_at'))
            elapsed = (g.datetime.now(g.timezone.utc) - deadline).total_seconds() if deadline else 0
            if len(checkpoint['votes']) >= len(party['members']) or elapsed >= 25:
                lead_state = self.state(leader, players[leader], checkpoint)
                if not lead_state.finalize_labyrinth_reward_vote():
                    raise ValueError(lead_state.labyrinth_status)
                checkpoint = g.capture_desktop_labyrinth(lead_state)
                # The browser game grants immediate gold on each client's floor
                # acknowledgement. A realm has no trusted client-side claims.
                effects = checkpoint['session']['modifier_stack'][-1].get('effects', {})
                bonus = max(0, int(effects.get('instant_gold_flat', 0)))
                entries = g._labyrinth_party_state_map(checkpoint['session']['pending_encounter'])
                for entry in entries.values():
                    if entry.get('player_snapshot'):
                        entry['player_snapshot']['gold'] += bonus
                checkpoint['session']['pending_encounter']['party_state'] = entries
                checkpoint['members'] = g._labyrinth_member_rows_from_party_state(checkpoint['members'], entries)
        party['checkpoint'] = checkpoint
        entries = g._labyrinth_party_state_map(checkpoint['session'].get('pending_encounter', {}))
        for uid in party['members']:
            entry = entries.get(uid)
            if entry and entry.get('player_snapshot'):
                raw = entry['player_snapshot']
                players[uid] = g.Player.from_dict(raw)
                players[uid].hp = entry['current_hp']
                players[uid].mana = entry['current_mana']
        return party, players
