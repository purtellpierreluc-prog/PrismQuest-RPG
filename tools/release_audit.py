"""Generate review inventories/notices; unresolved rights remain release blockers."""

import argparse
import csv
import hashlib
import importlib.metadata
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def inventory_assets(assets):
    rows = []
    for path in sorted(Path(assets).rglob('*')):
        if path.is_file():
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            rows.append({'path': path.relative_to(assets).as_posix(), 'sha256': digest, 'rights_status': 'UNREVIEWED', 'source_or_license': '', 'ai_status': 'UNCONFIRMED'})
    return rows


def generate(directory, assets, distributions=None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    packages = []
    notices = ['# Third-Party Build Environment Notices', '', 'Includes installed build/test tooling as well as runtime dependencies.',
               'Metadata is an inventory, not a legal clearance. Vendored assets, native runtime components,',
               'Microsoft redistribution terms, and game art/fonts/audio require separate review.', '']
    for distribution in distributions if distributions is not None else importlib.metadata.distributions():
        name = distribution.metadata.get('Name', 'unknown')
        safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', name)
        license_label = distribution.metadata.get('License-Expression') or distribution.metadata.get('License') or ''
        classifiers = [entry for entry in distribution.metadata.get_all('Classifier', []) if entry.startswith('License ::')]
        copied = []
        for relative in distribution.files or []:
            if not any(token in Path(relative).name.lower() for token in ('license', 'copying', 'copyright', 'notice')):
                continue
            if '..' in relative.parts or relative.is_absolute():
                continue
            source = Path(distribution.locate_file(relative))
            if source.is_file() and source.stat().st_size < 2_000_000:
                target = directory / 'third-party' / 'licenses' / safe_name / str(relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                copied.append(target.relative_to(directory).as_posix())
        package = {'name': name, 'version': distribution.version, 'license_metadata': license_label,
                   'license_classifiers': classifiers, 'license_files': copied,
                   'review_required': not copied}
        packages.append(package)
        notices.extend([f'## {name} {distribution.version}', license_label or '; '.join(classifiers) or 'License metadata unavailable: review required.',
                        'License text files: ' + (', '.join(copied) if copied else 'not found automatically; manual review required.'), ''])
    rows = inventory_assets(assets)
    with (directory / 'asset-rights-review.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['path', 'sha256', 'rights_status', 'source_or_license', 'ai_status'])
        writer.writeheader()
        writer.writerows(rows)
    report = {
        'scope': 'Inventory of installed build environment and game assets; not complete release approval.',
        'packages': sorted(packages, key=lambda item: item['name'].lower()), 'asset_count': len(rows),
        'blockers': ['Asset rights and AI/content disclosures need owner review.',
                     'Vendored JavaScript/fonts and native/Python/Microsoft runtime redistribution review is outstanding.',
                     'Steam account/configuration, clean-machine QA, and external playtest gates are not satisfied.'],
        'packages_missing_copied_license_text': [item['name'] for item in packages if item['review_required']],
        'release_approved': False,
    }
    (directory / 'third-party-inventory.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (directory / 'THIRD_PARTY_NOTICES.md').write_text('\n'.join(notices), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', default=str(ROOT / 'dist' / 'PrismQuest'))
    parser.add_argument('--assets', default=str(ROOT / 'Assets'))
    args = parser.parse_args()
    result = generate(args.directory, Path(args.assets))
    print(json.dumps({key: result[key] for key in ('asset_count', 'packages_missing_copied_license_text', 'release_approved')}, indent=2))
