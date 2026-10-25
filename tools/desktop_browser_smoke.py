"""Exercise a running desktop server with every external request blocked."""
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=8097)
parser.add_argument('--output', default='.local-test')
parser.add_argument('--quit', action='store_true', help='Exit the tested local game cleanly after validation.')
parser.add_argument('--resume-only', action='store_true', help='Verify an existing smoke-test character after restarting the app.')
args = parser.parse_args()
out = Path(args.output).resolve()
out.mkdir(parents=True, exist_ok=True)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe', headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    external = []
    errors = []
    def local_only(route):
        host = urlsplit(route.request.url).hostname
        if host in {'127.0.0.1', 'localhost'} or route.request.url.startswith(('data:', 'blob:')):
            route.continue_()
        else:
            external.append(route.request.url)
            route.abort()
    page.route('**/*', local_only)
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.goto(f'http://127.0.0.1:{args.port}', wait_until='networkidle')
    page.get_by_role('button', name='Play', exact=True).click()
    page.get_by_role('button', name='Open Core', exact=True).click()
    if not args.resume_only:
        page.get_by_label('Character Name', exact=True).fill('Steam Explorer')
        page.get_by_role('button', name='Enter the ascent as Black Guard', exact=True).click()
        page.get_by_role('button', name='Go to Arena', exact=True).click()
        page.get_by_text('Congratulations. That first Arena victory paid out a guaranteed Rare item.', exact=True).wait_for(timeout=45000)
        print('TUTORIAL', 'offline character creation and guaranteed Rare arena victory passed')
        page.get_by_role('button', name='Back to the Climb', exact=True).click()
        page.screenshot(path=str(out / 'offline-arena.png'), full_page=True)
        page.reload(wait_until='networkidle')
        page.get_by_text('Steam Explorer', exact=True).wait_for()
        page.get_by_role('button', name='Return to Town', exact=True).first.click()
        page.get_by_role('button', name='Chronicle Records', exact=True).click()
        page.get_by_text('Your local progression. Offline records are separate from the live online ladder.', exact=True).wait_for()
        page.get_by_role('button', name='Return to Town', exact=True).first.click()
        page.get_by_role('button', name='Quit to Title', exact=True).click()
        page.get_by_role('button', name='Play', exact=True).click()
        page.get_by_role('button', name='Open Core', exact=True).click()
    page.get_by_text('Steam Explorer the Black Guard', exact=True).first.wait_for()
    print('PERSISTENCE', 'saved character reopened' if args.resume_only else 'browser reload, local records, and title-screen reopen passed')
    print('EXTERNAL_REQUESTS', json.dumps(external))
    print('PAGE_ERRORS', json.dumps(errors))
    assert not external and not errors
    if args.quit:
        page.get_by_role('button', name='Quit to Title', exact=True).click()
        page.get_by_role('button', name='Quit Game', exact=True).click()
    browser.close()
