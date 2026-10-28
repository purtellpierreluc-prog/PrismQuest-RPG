"""Viewport/interaction checks against a running isolated desktop profile."""

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=8099)
parser.add_argument('--output', default='.local-test/layout')
parser.add_argument('--live-css', action='store_true', help='Developer-only CSS iteration without restarting the test server.')
args = parser.parse_args()
out = Path(args.output)
out.mkdir(parents=True, exist_ok=True)
sys.stdout.reconfigure(encoding='utf-8')


def check_layout(page, scene, controls=(), selectors=()):
    page.wait_for_timeout(250)
    page.screenshot(path=str(out / f'{scene}-{page.viewport_size["width"]}x{page.viewport_size["height"]}.png'))
    metrics = page.evaluate('''() => {
      const rect = document.querySelector('.mq-desktop').getBoundingClientRect();
      return {width: innerWidth, height: innerHeight, pageHeight: document.scrollingElement.scrollHeight,
        pageWidth: document.scrollingElement.scrollWidth, bottom: rect.bottom, right: rect.right};
    }''')
    assert metrics['pageHeight'] <= metrics['height'] + 1, (scene, metrics)
    assert metrics['pageWidth'] <= metrics['width'] + 1, (scene, metrics)
    assert metrics['bottom'] <= metrics['height'] + 1, (scene, metrics)
    for name in controls:
        button = page.get_by_role('button', name=name, exact=True).first
        box = button.bounding_box()
        assert box and box['y'] >= 0 and box['y'] + box['height'] <= metrics['height'] + 1, (scene, name, box)
    for selector in selectors:
        for element in page.locator(selector).all():
            outside = element.evaluate('''e => {
              if (getComputedStyle(e).display === 'contents') return [];
              const box = e.getBoundingClientRect();
              return [...e.children].filter(child => {
                const style = getComputedStyle(child), r = child.getBoundingClientRect();
                if (['absolute','fixed'].includes(style.position) || style.display === 'none' || !r.height) return false;
                return r.top < box.top - 2 || r.bottom > box.bottom + 2;
              }).map(child => ({class:child.className, bottom:child.getBoundingClientRect().bottom, parentBottom:box.bottom}));
            }''')
            assert not outside, (scene, selector, outside)
    print(json.dumps({'scene': scene, **metrics}), flush=True)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe', headless=True)
    page = browser.new_page(viewport={'width': 1366, 'height': 768})
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
    page.evaluate('() => document.fonts.ready')
    assert page.evaluate('document.documentElement.dataset.pqNocturne === "true"')
    assert page.evaluate('document.fonts.check("16px Cinzel") && document.fonts.check("16px Barlow")')
    play = page.get_by_role('button', name='Play', exact=True)
    assert play.evaluate('e => getComputedStyle(e).color') == 'rgb(27, 25, 20)'
    assert play.get_attribute('data-mq-paint-theme') is None
    assert play.get_attribute('style') is None
    font = page.request.get(f'http://127.0.0.1:{args.port}/desktop-ui/fonts/Cinzel.ttf')
    assert font.status == 200 and 'max-age=31536000' in font.headers.get('cache-control', '')
    page.emulate_media(reduced_motion='reduce')
    assert page.locator('.mq-title-side-stack').evaluate('e => getComputedStyle(e).animationName') == 'none'
    page.emulate_media(reduced_motion='no-preference')
    if args.live_css:
        page.add_style_tag(path=str(Path(__file__).resolve().parents[1] / 'steam_client' / 'static' / 'desktop.css'))
    sizes = [(1280, 720), (1366, 768), (1920, 1080), (960, 600), (2560, 1080), (800, 500)]
    for width, height in sizes:
        page.set_viewport_size({'width': width, 'height': height})
        check_layout(page, 'title', ['Play', 'Quit Game'])
        image = page.locator('.mq-title-image-static')
        assert image.evaluate('(e) => e.complete && e.naturalWidth > 0 && getComputedStyle(e).objectFit === "contain"')
        assert image.evaluate('''e => {
          const a = e.getBoundingClientRect(), b = e.closest('.mq-title-stage').getBoundingClientRect();
          return a.top >= b.top && a.bottom <= b.bottom + 1 && a.left >= b.left && a.right <= b.right + 1;
        }''')
    page.set_viewport_size({'width': 1366, 'height': 768})
    page.get_by_role('button', name='Play', exact=True).click()
    check_layout(page, 'chronicle', ['Open Core', 'Open SSF', 'Open HC'])
    page.get_by_role('button', name='Open Core', exact=True).click()
    page.get_by_label('Character Name', exact=True).or_(page.get_by_role('button', name='Arena', exact=True)).first.wait_for()
    if page.get_by_label('Character Name', exact=True).count():
        page.get_by_label('Character Name', exact=True).fill('Desktop Explorer')
        page.get_by_role('button', name='Enter the ascent as Black Guard', exact=True).click()
        page.set_viewport_size({'width': 960, 'height': 600})
        check_layout(page, 'town-tutorial', ['Go to Arena'])
        page.get_by_role('button', name='Go to Arena', exact=True).click()
        page.get_by_text('Congratulations. That first Arena victory paid out a guaranteed Rare item.', exact=True).wait_for(timeout=45000)
        check_layout(page, 'arena-tutorial', ['Back to the Climb'])
        page.get_by_role('button', name='Back to the Climb', exact=True).click()
    else:
        page.get_by_role('button', name='Arena', exact=True).click()
    page.get_by_role('button', name='Fight', exact=True).click()
    expect(page.get_by_role('button', name='Fight', exact=True)).to_be_disabled(timeout=15000)
    page.locator('.mq-monster-image-static').first.wait_for()
    expect(page.get_by_role('button', name='Fight', exact=True)).to_be_enabled(timeout=90000)
    for width, height in sizes:
        page.set_viewport_size({'width': width, 'height': height})
        check_layout(page, 'arena', ['Fight', 'Inventory', 'Return to Town'], ['.mq-arena-top > .mq-arena-card', '.mq-player-side-layout', '.mq-player-side-layout > .nicegui-column', '.mq-monster-details'])
        assert page.locator('.mq-player-summary-grid').bounding_box()['y'] + page.locator('.mq-player-summary-grid').bounding_box()['height'] <= page.locator('.mq-player-side-layout').bounding_box()['y'] + page.locator('.mq-player-side-layout').bounding_box()['height'] + 2
    page.get_by_role('button', name='Return to Town', exact=True).first.click()
    for width, height in sizes:
        page.set_viewport_size({'width': width, 'height': height})
        check_layout(page, 'town', ['Arena', 'Settings', 'Quit to Title'], ['.mq-town-dashboard > .q-card'])
        assert page.locator('.mq-town-scene-stage').bounding_box()['height'] > 100
    page.set_viewport_size({'width': 1280, 'height': 720})
    page.get_by_role('button', name='Settings', exact=True).click()
    page.get_by_role('button', name='Desktop', exact=True).click()
    check_layout(page, 'desktop-settings', ['Create Manual Backup', 'Open Save Folder', 'Return to Town'])
    page.get_by_role('button', name='Create Manual Backup', exact=True).click()
    page.get_by_text('Backup created:', exact=False).wait_for()
    print('EXTERNAL_REQUESTS', external, 'PAGE_ERRORS', errors)
    assert not external and not errors
    browser.close()
