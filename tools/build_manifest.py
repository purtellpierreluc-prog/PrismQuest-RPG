"""Generate a build inventory for diagnostics and distribution integrity checks."""

import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from steam_client import __version__


def build_manifest(directory):
    directory = Path(directory).resolve()
    if not (directory / 'PrismQuest.exe').is_file():
        raise FileNotFoundError('No packaged PrismQuest.exe was found.')
    files = {}
    for path in sorted(directory.rglob('*')):
        if path.is_file() and path.name != 'build-info.json':
            with path.open('rb') as stream:
                files[path.relative_to(directory).as_posix()] = hashlib.file_digest(stream, 'sha256').hexdigest()
    payload = {
        'product': 'PrismQuest', 'version': __version__, 'build_time': datetime.now(UTC).isoformat(),
        'python': platform.python_version(), 'platform': platform.platform(),
        'build_packages': {distribution.metadata['Name']: distribution.version for distribution in importlib.metadata.distributions()},
        'files_sha256': files,
        'note': 'Build inventory, not a completed third-party license audit or a signed release.',
    }
    target = directory / 'build-info.json'
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding='utf-8')
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    print(build_manifest(parser.parse_args().directory))
