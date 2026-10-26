"""Exercise service panes, item dialogs, and a five-member Labyrinth fixture."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=8101)
parser.add_argument('--output', default='.local-test/advanced-layout')
parser.add_argument('--live-css', action='store_true')
args = parser.parse_args()
out = Path(args.output)
out.mkdir(parents=True, exist_ok=True)


def check(page, name, controls=()):
    page.wait_for_timeout(300)
    page.screenshot(path=str(out / f'{name}-{page.viewport_size["width"]}.png'))
    metrics = page.evaluate('() => ({w:innerWidth,h:innerHeight,sw:document.scrollingElement.scrollWidth,sh:document.scrollingElement.scrollHeight})')
    assert metrics['sw'] <= metrics['w'] + 1 and metrics['sh'] <= metrics['h'] + 1, metrics
    for control in controls:
        box = page.get_by_role('button', name=control, exact=True).first.bounding_box()
        assert box and box['y'] >= 0 and box['y'] + box['height'] <= metrics['h'] + 2, (name, control, box)
    print(json.dumps({'scene': name, **metrics}), flush=True)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe', headless=True)
    page = b.new_page(viewport={'width': 1280, 'height': 720})
    errors, external = [], []

    def local_only(route):
        if urlsplit(route.request.url).hostname in {'127.0.0.1', 'localhost'}:
            route.continue_()
        else:
            external.append(route.request.url)
            route.abort()

    page.route('**/*', local_only)
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(f'http://127.0.0.1:{args.port}', wait_until='networkidle')
    if args.live_css:
        page.add_style_tag(path=str(Path(__file__).resolve().parents[1] / 'steam_client' / 'static' / 'desktop.css'))
    page.get_by_role('button', name='Play', exact=True).click()
    page.get_by_role('button', name='Open Core', exact=True).click()
    for route in ['Inn', 'Marketplace', 'Transmutation', 'Well of Evil', 'Glossary', 'Chronicle Records', 'Settings', 'Labyrinth of Light']:
        page.get_by_role('button', name=route, exact=True).click()
        for width, height in [(1280, 720), (960, 600), (1920, 1080)]:
            page.set_viewport_size({'width': width, 'height': height})
            check(page, route.replace(' ', '-'), ['Return to Town'])
        if route == 'Inn':
            page.set_viewport_size({'width': 1280, 'height': 720})
            page.get_by_role('button', name='Open Vault', exact=True).click()
            for width, height in [(1280, 720), (960, 600)]:
                page.set_viewport_size({'width': width, 'height': height})
                check(page, 'vault', ['Close', 'Deposit Selected', 'Withdraw Selected'])
            page.get_by_role('button', name='Close', exact=True).click()
        page.get_by_role('button', name='Return to Town', exact=True).first.click()
    page.set_viewport_size({'width': 1280, 'height': 720})
    page.get_by_role('button', name='Inventory', exact=True).click()
    for width, height in [(1280, 720), (960, 600), (1920, 1080)]:
        page.set_viewport_size({'width': width, 'height': height})
        check(page, 'inventory', ['Close', 'Equip Selected', 'Sell Selected'])
    close_id = page.get_by_role('button', name='Close', exact=True).get_attribute('id')
    page.locator('.mq-manifest-entry-card').nth(1).hover()
    page.wait_for_timeout(350)
    assert page.get_by_role('button', name='Close', exact=True).get_attribute('id') == close_id
    page.get_by_role('button', name='Saved Sets', exact=True).click()
    check(page, 'saved-sets', ['Close'])
    page.get_by_role('button', name='Close', exact=True).click()
    page.get_by_role('button', name='Arena', exact=True).wait_for()
    page.get_by_role('button', name='Return to Chronicle Slots', exact=True).click()
    page.get_by_text('Chronicle Slots', exact=True).wait_for()
    page.get_by_role('button', name='Open SSF', exact=True).click()
    page.locator('.mq-lab-grid').wait_for()
    for width, height in [(1280, 720), (960, 600), (1920, 1080)]:
        page.set_viewport_size({'width': width, 'height': height})
        check(page, 'labyrinth', ['Return to Town'])
        frame = page.locator('.mq-lab-grid').bounding_box()
        assert frame['y'] + frame['height'] <= height and frame['height'] > 150, frame
        assert page.locator('.mq-lab-member-card').count() == 5
        assert page.locator('.mq-lab-member-card').evaluate_all('''cards => cards.every(card => {
          const c = card.getBoundingClientRect();
          return [...card.querySelectorAll('.mq-meter-track')].every(meter => {
            const m = meter.getBoundingClientRect();
            return m.top >= c.top && m.bottom <= c.bottom + 2;
          });
        })''')
    page.set_viewport_size({'width': 1280, 'height': 720})
    tank = page.locator('.mq-lab-member-card').first.locator('.mq-lab-tank-btn')
    if tank.inner_text().strip() == 'T OFF':
        tank.click()
    expect(tank).to_have_attribute('aria-pressed', 'true')
    assert tank.evaluate('(e) => getComputedStyle(e).borderTopColor') == 'rgb(128, 228, 172)'
    page.get_by_text('Movement & Companions', exact=True).click()
    page.get_by_role('button', name='Open Inventory', exact=True).click()
    check(page, 'lab-inventory', ['Close'])
    page.get_by_role('button', name='Close', exact=True).click()
    page.locator('.mq-lab-grid').wait_for()
    before = page.locator('.mq-lab-tile').all_inner_texts().index('P')
    page.keyboard.press('ArrowRight')
    page.wait_for_function('before => !document.querySelector(".mq-lab-grid") || [...document.querySelectorAll(".mq-lab-tile")].findIndex(e=>e.textContent.trim()==="P") !== before', arg=before)
    print('KEYBOARD_MOVE passed')
    print('EXTERNAL_REQUESTS', external, 'PAGE_ERRORS', errors)
    assert not external and not errors
    b.close()
