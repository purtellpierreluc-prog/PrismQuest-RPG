"""Generate preview-only SteamPipe files; never authenticate, upload, or set live."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from steam_client.diagnostics import verify_package


def steam_id(value):
    if not str(value).isdecimal() or int(value) <= 0 or int(value) == 480:
        raise ValueError('Supply your own positive Steamworks ID, not an example/test App ID.')
    return str(int(value))


def vdf_quote(value):
    text = str(value)
    if any(character in text for character in ('"', '\n', '\r', '\0')):
        raise ValueError('Unsafe VDF string.')
    return '"' + text.replace('\\', '/') + '"'


def render(app_id, depot_id, content_root, output):
    app_id, depot_id = steam_id(app_id), steam_id(depot_id)
    app = '\n'.join([
        '"AppBuild"', '{', f'  "AppID" "{app_id}"',
        '  "Desc" "PrismQuest Windows preview - verify in Steamworks before upload"',
        '  "Preview" "1"', f'  "ContentRoot" {vdf_quote(Path(content_root).resolve())}',
        f'  "BuildOutput" {vdf_quote(Path(output).resolve() / "cache")}',
        '  "Depots"', '  {', f'    "{depot_id}" "depot_build_{depot_id}.vdf"', '  }', '}', '',
    ])
    depot = '\n'.join([
        '"DepotBuild"', '{', f'  "DepotID" "{depot_id}"', '  "FileMapping"', '  {',
        '    "LocalPath" "*"', '    "DepotPath" "."', '    "Recursive" "1"', '  }',
        '  "FileExclusion" "steam_appid.txt"', '  "FileExclusion" "*.pdb"', '}', '',
    ])
    return app, depot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-id', required=True)
    parser.add_argument('--depot-id', required=True)
    parser.add_argument('--content', default=str(ROOT / 'dist' / 'PrismQuest'))
    parser.add_argument('--output', default=str(ROOT / 'build' / 'steampipe'))
    args = parser.parse_args()
    if not verify_package(args.content)['valid']:
        raise SystemExit('Package verification failed; no upload files generated.')
    app, depot = render(args.app_id, args.depot_id, args.content, args.output)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    for name, text in [(f'app_build_{steam_id(args.app_id)}.vdf', app), (f'depot_build_{steam_id(args.depot_id)}.vdf', depot)]:
        target = output / name
        with target.open('x', encoding='utf-8') as stream:
            stream.write(text)
        print(target)
    print('Preview only. Nothing uploaded. No branch was set live. Never place credentials in these files.')


if __name__ == '__main__':
    main()
