"""Atomic local saves, with recovery copies and explicit failure reporting."""

import hashlib
import json
import logging
import os
import shutil
import tempfile
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .save_schema import CURRENT_SAVE_VERSION, validate_slots

LOGGER = logging.getLogger(__name__)
_UNOBSERVED = object()


class SaveRecoveryRequired(RuntimeError):
    pass


class UnsupportedSaveVersion(SaveRecoveryRequired):
    pass


class SaveConflictError(SaveRecoveryRequired):
    pass


class AtomicSaveStore:
    def __init__(self, path, backups=None):
        self.path = Path(path)
        self.backups = Path(backups) if backups else self.path.parent / 'backups'
        self.lock = threading.RLock()
        self._observed_digest = _UNOBSERVED
        self.recovery_source = None
        self.metrics = {'writes': 0, 'skipped': 0, 'bytes_written': 0, 'write_seconds': 0.0}

    @staticmethod
    def _validate(payload):
        if not isinstance(payload, dict):
            raise TypeError('Save document must be an object.')
        version = payload.get('format_version', 1)
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise ValueError('Invalid save format version.')
        if version > CURRENT_SAVE_VERSION:
            raise UnsupportedSaveVersion('This save requires a newer game version. It has not been changed.')
        slots = validate_slots(payload.get('slots'))
        checksum = payload.get('checksum')
        if version >= 2 and (not isinstance(checksum, str) or len(checksum) != 64):
            raise ValueError('Versioned save is missing its integrity checksum.')
        if checksum and checksum != AtomicSaveStore._checksum(slots):
            raise ValueError('Save checksum does not match.')
        return slots

    @staticmethod
    def _checksum(slots):
        raw = json.dumps(slots, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def _read(self, path):
        return self._validate(json.loads(path.read_text(encoding='utf-8-sig')))

    def load(self):
        with self.lock:
            self.recovery_source = None
            primary = self.path.read_bytes() if self.path.exists() else None
            self._observed_digest = hashlib.sha256(primary).hexdigest() if primary is not None else None
            if not self.path.exists() and not self.backups.exists():
                return None
            errors = []
            candidates = [self.path] + sorted(self.backups.glob('chronicles-*.json'), reverse=True)
            for candidate in candidates:
                if not candidate.exists():
                    continue
                try:
                    result = self._validate(json.loads(primary.decode('utf-8-sig'))) if candidate == self.path else self._read(candidate)
                    if candidate != self.path:
                        self.recovery_source = candidate.name
                        LOGGER.warning('Recovered a local save from a rotating backup; unreadable primary preserved.')
                    return result
                except (OSError, ValueError, TypeError) as exc:
                    errors.append(f'{candidate.name}: {exc}')
            if errors:
                raise SaveRecoveryRequired('No valid save could be recovered. Files have been preserved. ' + '; '.join(errors))
            return None

    def save(self, slots):
        payload = {
            'format_version': CURRENT_SAVE_VERSION,
            'saved_at': datetime.now(UTC).isoformat(),
            'checksum': self._checksum(slots),
            'slots': slots,
        }
        self._validate(payload)
        encoded = json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
        with self.lock:
            started = time.perf_counter()
            current = self.path.read_bytes() if self.path.exists() else None
            current_digest = hashlib.sha256(current).hexdigest() if current is not None else None
            if self._observed_digest is not _UNOBSERVED and current_digest != self._observed_digest:
                raise SaveConflictError('The save changed outside this game session. Close the game and reopen it to load the changed save. Existing files were preserved.')
            if current is not None:
                current_payload = json.loads(current.decode('utf-8-sig')) if self.recovery_source is None else None
                if current_payload is not None:
                    self._validate(current_payload)
                    if current_payload.get('format_version') == CURRENT_SAVE_VERSION and current_payload.get('checksum') == payload['checksum']:
                        self._observed_digest = current_digest
                        self.metrics['skipped'] += 1
                        return False
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.backups.mkdir(parents=True, exist_ok=True)
            if self.path.exists():
                try:
                    self._read(self.path)
                except (OSError, ValueError, TypeError):
                    # Never replace a known-good backup with a broken primary save.
                    corrupt = self.backups / ('unreadable-' + datetime.now(UTC).strftime('%Y%m%d-%H%M%S-%f') + '.json')
                    shutil.copy2(self.path, corrupt)
                else:
                    name = 'chronicles-' + datetime.now(UTC).strftime('%Y%m%d-%H%M%S-%f') + '.json'
                    shutil.copy2(self.path, self.backups / name)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=self.path.parent, prefix='.chronicles-', suffix='.tmp', delete=False) as handle:
                    temporary = Path(handle.name)
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.path)
                self._observed_digest = hashlib.sha256(encoded).hexdigest()
                self.recovery_source = None
                self.metrics['writes'] += 1
                self.metrics['bytes_written'] += len(encoded)
                self.metrics['write_seconds'] += time.perf_counter() - started
            finally:
                if temporary and temporary.exists():
                    temporary.unlink()
            for old in sorted(self.backups.glob('chronicles-*.json'), reverse=True)[10:]:
                try:
                    old.unlink()
                except OSError:
                    LOGGER.warning('Could not prune an old rotating backup; the current save committed successfully.')
            return True

    def create_manual_backup(self):
        with self.lock:
            self._read(self.path)
            self.backups.mkdir(parents=True, exist_ok=True)
            name = 'manual-' + datetime.now(UTC).strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8] + '.json'
            target = self.backups / name
            created = False
            try:
                with target.open('xb') as stream:
                    created = True
                    stream.write(self.path.read_bytes())
                    stream.flush()
                    os.fsync(stream.fileno())
            except OSError:
                if created:
                    target.unlink(missing_ok=True)
                raise
            return target


class SingleInstance:
    def __init__(self, path):
        self.path = Path(path)
        self.handle = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open('a+b')
        if self.path.stat().st_size == 0:
            self.handle.write(b'1')
            self.handle.flush()
        self.handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.handle.close()
            self.handle = None
            raise RuntimeError('PrismQuest is already running for this local profile.') from None
        return self

    def release(self):
        if self.handle is not None:
            self.handle.close()
            self.handle = None
