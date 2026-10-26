"""Atomic local saves, with recovery copies and explicit failure reporting."""

import hashlib
import json
import os
import shutil
import tempfile
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path


class SaveRecoveryRequired(RuntimeError):
    pass


class UnsupportedSaveVersion(SaveRecoveryRequired):
    pass


class AtomicSaveStore:
    def __init__(self, path, backups=None):
        self.path = Path(path)
        self.backups = Path(backups) if backups else self.path.parent / 'backups'
        self.lock = threading.RLock()

    @staticmethod
    def _validate(payload):
        if not isinstance(payload, dict):
            raise TypeError('Save document must be an object.')
        if payload.get('format_version', 1) != 1:
            raise UnsupportedSaveVersion('This save requires a newer game version. It has not been changed.')
        slots = payload.get('slots')
        if not isinstance(slots, list) or len(slots) != 3 or not all(isinstance(slot, dict) for slot in slots):
            raise ValueError('Save document must contain three chronicle slots.')
        checksum = payload.get('checksum')
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
            if not self.path.exists() and not self.backups.exists():
                return None
            errors = []
            candidates = [self.path] + sorted(self.backups.glob('chronicles-*.json'), reverse=True)
            for candidate in candidates:
                if not candidate.exists():
                    continue
                try:
                    return self._read(candidate)
                except (OSError, ValueError, TypeError) as exc:
                    errors.append(f'{candidate.name}: {exc}')
            if errors:
                raise SaveRecoveryRequired('No valid save could be recovered. Files have been preserved. ' + '; '.join(errors))
            return None

    def save(self, slots):
        payload = {
            'format_version': 1,
            'saved_at': datetime.now(UTC).isoformat(),
            'checksum': self._checksum(slots),
            'slots': slots,
        }
        self._validate(payload)
        encoded = json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
        with self.lock:
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
            finally:
                if temporary and temporary.exists():
                    temporary.unlink()
            for old in sorted(self.backups.glob('chronicles-*.json'), reverse=True)[10:]:
                old.unlink()

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
