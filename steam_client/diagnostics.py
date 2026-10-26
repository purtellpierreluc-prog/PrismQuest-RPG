"""On-demand local diagnostics; no telemetry, account data, or log uploads."""

import hashlib
import json
import platform
import struct
import sys
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from . import __version__
from .storage import AtomicSaveStore, SaveRecoveryRequired


def webview_version():
    if sys.platform != 'win32':
        return None
    import winreg
    key = r'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            try:
                with winreg.OpenKey(hive, key, 0, winreg.KEY_READ | view) as handle:
                    value = str(winreg.QueryValueEx(handle, 'pv')[0])
                    if all(part.isdecimal() for part in value.split('.')) and any(int(part) for part in value.split('.')):
                        return value
            except OSError:
                continue
    return None


def check_native_prerequisites():
    if sys.platform != 'win32' or struct.calcsize('P') != 8:
        raise RuntimeError('This desktop build requires 64-bit Windows. Browser diagnostics are development-only.')
    if not webview_version():
        raise RuntimeError('Microsoft Edge WebView2 Runtime was not detected. Install the Evergreen Runtime from https://developer.microsoft.com/microsoft-edge/webview2/ then reopen PrismQuest. No save was changed.')


def verify_package(directory):
    root = Path(directory).resolve()
    manifest = json.loads((root / 'build-info.json').read_text(encoding='utf-8'))
    entries = manifest['files_sha256']
    if not isinstance(entries, dict) or not entries:
        raise ValueError('Empty package inventory.')
    changed = []
    for name, expected in entries.items():
        relative = PurePosixPath(name)
        target = (root / name).resolve()
        if relative.is_absolute() or '..' in relative.parts or not target.is_relative_to(root):
            raise ValueError('Unsafe package inventory path.')
        if not target.is_file():
            changed.append(name)
            continue
        with target.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                changed.append(name)
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.name != 'build-info.json'}
    unexpected = sorted(actual - set(entries))
    return {'valid': not changed and not unexpected, 'files_checked': len(entries), 'changed': changed, 'unexpected': unexpected}


def collect_diagnostics(paths, store=None):
    reader = AtomicSaveStore(paths.save_file, paths.backups)
    try:
        slots = reader.load()
        saves = {'status': 'ok' if slots else 'new_profile', 'occupied_slots': sum(bool(slot.get('player')) for slot in slots or []), 'recovered_backup': reader.recovery_source is not None}
    except (OSError, ValueError, TypeError, SaveRecoveryRequired) as exc:
        saves = {'status': type(exc).__name__}
    return {
        'product': 'PrismQuest', 'version': __version__, 'created_utc': datetime.now(UTC).isoformat(),
        'system': {'os': platform.system(), 'release': platform.release(), 'machine': platform.machine(), 'python': platform.python_version(), 'bits': struct.calcsize('P') * 8, 'webview2': webview_version()},
        'saves': saves, 'save_metrics': dict(store.metrics) if store else {},
        'privacy': 'Local report only. No names, items, absolute paths, saves, account IDs, environment variables, or log contents included.',
        'steam': {'sdk_integrated': False, 'overlay_verified': False, 'cloud_enabled': False},
    }


def write_diagnostics(paths, store=None):
    target = paths.logs / ('diagnostics-' + datetime.now(UTC).strftime('%Y%m%d-%H%M%S-%f') + '.json')
    target.write_text(json.dumps(collect_diagnostics(paths, store), indent=2), encoding='utf-8')
    return target
