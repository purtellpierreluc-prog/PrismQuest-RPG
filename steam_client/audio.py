"""Independent local audio preferences and read-only presentation signals."""

import asyncio
import json
import logging
import math
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class AudioPreferences:
    effects_volume: int = 35
    music_volume: int = 18
    muted: bool = False
    music_enabled: bool = True
    combat_enabled: bool = True
    rewards_enabled: bool = True
    mute_unfocused: bool = True

    @classmethod
    def from_payload(cls, payload):
        defaults = cls()
        if not isinstance(payload, dict):
            return defaults
        values = asdict(defaults)
        for key, fallback in values.items():
            value = payload.get(key, fallback)
            if isinstance(fallback, bool):
                values[key] = value if isinstance(value, bool) else fallback
            else:
                try:
                    number = float(value)
                    values[key] = max(0, min(100, round(number))) if not isinstance(value, bool) and math.isfinite(number) else fallback
                except (TypeError, ValueError, OverflowError):
                    values[key] = fallback
        return cls(**values)


class DesktopAudio:
    def __init__(self, path):
        self.path = Path(path)
        self.pending = None
        self.preferences = AudioPreferences()
        try:
            self.preferences = AudioPreferences.from_payload(json.loads(self.path.read_text(encoding='utf-8')))
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError):
            LOGGER.warning('Audio preferences could not be read; using quiet defaults.')

    def payload(self):
        return asdict(self.preferences)

    def set(self, key, value):
        if key not in self.payload():
            raise ValueError('Unknown audio preference.')
        normalized = AudioPreferences.from_payload({**self.payload(), key: value})
        if normalized == self.preferences:
            return
        self.preferences = normalized
        if self.pending is not None:
            self.pending.cancel()
        try:
            self.pending = asyncio.get_running_loop().call_later(.4, self._safe_save)
        except RuntimeError:
            self._safe_save()

    def reset(self):
        self.preferences = AudioPreferences()
        self.flush()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.path.parent, prefix='.audio-', suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(json.dumps(self.payload(), sort_keys=True).encode('utf-8'))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    def _safe_save(self):
        self.pending = None
        try:
            self.save()
        except OSError:
            LOGGER.exception('Could not save audio preferences; character saves were not touched.')

    def flush(self):
        if self.pending is not None:
            self.pending.cancel()
            self.pending = None
        self._safe_save()


def audio_signal(state):
    """Small metadata on an existing render, never an extra game timer/message."""
    player = state.player
    if player is None or state.screen not in {'town', 'game'}:
        return {'p': '', 's': state.screen, 'a': False}
    scene = state.game_tab if state.screen == 'game' else 'town'
    lab = getattr(state, 'labyrinth_session_row', {}) or {}
    lab_active = scene == 'labyrinth' and lab.get('status') in {'encounter', 'boss'}
    monster = getattr(state, 'current_monster', None)
    item = getattr(state, 'last_monster_drop_item', None)
    player_hit = float(getattr(state, 'player_damage_popup_at', 0))
    monster_hit = float(getattr(state, 'monster_damage_popup_at', 0))
    pending = lab.get('pending_encounter', {}) or {}
    encounter = f'lab:{lab.get("id", "")}:{lab.get("floor", 0)}:{pending.get("started_at", "")}' if scene == 'labyrinth' else int(getattr(state, '_experience_serial', 0))
    outcome = ('defeat' if lab.get('status') == 'defeated' else 'victory' if lab.get('status') in {'exploring', 'reward'} else 'idle') if scene == 'labyrinth' else str(getattr(state, 'last_fight_outcome', 'idle'))
    caster = player.player_class in {'Shadow Mage', 'Warlock', 'Prismatic Sorceress', 'Shadow Arcanist', 'Night Angel', 'Frost Oracle', 'Ember Fae'}
    return {
        'p': f'{state.active_slot_index}:{player.name}:{player.player_class}',
        's': scene, 'a': bool(state.fight_in_progress or lab_active), 'l': player.level,
        'r': int(getattr(state, 'last_monster_drop_sequence', 0)), 'q': str(getattr(item, 'rarity', 'Common')),
        'h': player.hp, 'm': int(getattr(monster, 'hp', 0)),
        'd': max(player_hit, monster_hit),
        'c': bool(getattr(state, 'player_damage_popup_crit' if player_hit >= monster_hit else 'monster_damage_popup_crit', False)),
        'k': 'spell' if caster else 'impact',
        'e': encounter, 'o': outcome,
    }
