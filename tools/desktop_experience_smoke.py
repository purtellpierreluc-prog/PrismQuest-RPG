"""Exercise the reimagined decision loop on a disposable local profile."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--seeded', action='store_true')
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    sizes = [(1280, 720), (1366, 768), (1920, 1080), (960, 600), (2560, 1080), (800, 500)]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe', headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 720})
        external, errors = [], []

        def route(request):
            if urlsplit(request.request.url).hostname in {'127.0.0.1', 'localhost'}:
                request.continue_()
            else:
                external.append(request.request.url)
                request.abort()

        def check(name, controls=(), selectors=()):
            page.wait_for_timeout(250)
            metrics = page.evaluate('() => ({w:innerWidth,h:innerHeight,sw:document.scrollingElement.scrollWidth,sh:document.scrollingElement.scrollHeight})')
            assert metrics['sw'] <= metrics['w'] + 1 and metrics['sh'] <= metrics['h'] + 1, (name, metrics)
            for label in controls:
                box = page.get_by_role('button', name=label, exact=True).first.bounding_box()
                assert box and box['y'] >= 0 and box['y']+box['height'] <= metrics['h'] + 1, (name, label, box)
            for selector in selectors:
                expect(page.locator(selector).first).to_be_visible()
                # Sample a refreshable combat region in one browser task instead
                # of retaining nodes across a round's DOM replacement.
                boxes = page.locator(selector).evaluate_all('els => els.map(e => { const r=e.getBoundingClientRect(); return {y:r.y,height:r.height}; })')
                assert boxes, (name, selector)
                for box in boxes:
                    assert box['height'] > 0 and box['y'] >= 0 and box['y']+box['height'] <= metrics['h'] + 1, (name, selector, box)
            page.screenshot(path=str(out / f'{name}-{metrics["w"]}.png'))
            print(json.dumps({'scene': name, **metrics}), flush=True)

        def menu(label):
            page.wait_for_timeout(200)
            page.get_by_role('button', name='Chronicle Menu', exact=True).click()
            page.get_by_text(label, exact=True).last.click()

        def town():
            page.get_by_role('button', name='Return to Town', exact=True).first.click()
            page.locator('.pd-town-workspace').wait_for()

        page.route('**/*', route)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(f'http://127.0.0.1:{args.port}', wait_until='networkidle')
        page.evaluate('() => document.fonts.ready')
        for width, height in sizes:
            page.set_viewport_size({'width': width, 'height': height})
            check('title', ['Play', 'Quit Game'])
        page.set_viewport_size({'width': 1280, 'height': 720})
        page.get_by_role('button', name='Play', exact=True).click()
        page.get_by_role('button', name='Open Core', exact=True).click()
        if not args.seeded:
            page.get_by_label('Character Name', exact=True).fill('Prism Explorer')
            page.get_by_role('button', name='Enter the ascent as Black Guard', exact=True).click()
            check('town-tutorial', ['Go to Arena'])
            page.get_by_role('button', name='Go to Arena', exact=True).click()
            page.get_by_text('Congratulations. That first Arena victory paid out a guaranteed Rare item.', exact=True).wait_for(timeout=60000)
            page.get_by_role('button', name='Back to the Climb', exact=True).click()
            page.locator('.pd-result-title.victory').wait_for()
            assert 'XP progress' in page.locator('.pd-reward-totals').inner_text()
            assert 'RARE' in page.locator('.pd-found-item').inner_text()
            page.wait_for_function('window.PrismAudio.inspect().played.find_rare === 1')
            for width, height in sizes:
                page.set_viewport_size({'width': width, 'height': height})
                check('victory', ['Fight', 'Inspect This Find', 'Inventory'], ['.pd-actor-resources', '.pd-command-deck'])
            assert page.evaluate('window.PrismAudio.inspect().played.find_rare') == 1
            page.set_viewport_size({'width': 1280, 'height': 720})
            page.get_by_role('button', name='Inspect This Find', exact=True).click()
            page.locator('.pd-equipment-decision').wait_for()
            assert page.locator('.mq-inv-detail-panel').first.inner_text().lower().startswith('selected find')
            check('first-upgrade', ['Equip Selected', 'Close'])
            page.get_by_role('button', name='Equip Selected', exact=True).click()
            page.get_by_role('button', name='Close', exact=True).click()
            page.get_by_role('button', name='Fight', exact=True).click()
            expect(page.get_by_role('button', name='Fight', exact=True)).to_be_disabled(timeout=15000)
            check('combat', ['Fight'], ['.pd-actor-resources'])
            expect(page.get_by_role('button', name='Fight', exact=True)).to_be_enabled(timeout=90000)
            town()
        else:
            page.locator('.pd-town-workspace').wait_for()
        for width, height in sizes:
            page.set_viewport_size({'width': width, 'height': height})
            check('town', ['Arena', 'Inn', 'Marketplace', 'Settings', 'Quit to Title'], ['.pd-destination-deck', '.pd-service-deck'])
        page.set_viewport_size({'width': 1280, 'height': 720})
        page.get_by_role('button', name='Inventory', exact=True).first.click()
        page.locator('.pd-equipment-inspector').wait_for()
        menu('Tutorial')
        page.get_by_text('Inventory Tutorial', exact=True).wait_for()
        page.get_by_role('button', name='Back to the Climb', exact=True).click()
        for width, height in sizes[:4]:
            page.set_viewport_size({'width': width, 'height': height})
            check('armory', ['Close', 'Equip Selected', 'Sell Selected'])
        if args.seeded:
            cards = page.locator('.mq-manifest-entry-card')
            cards.nth(1).click()
            expect(cards.nth(1).locator('.mq-manifest-flag.selected')).to_be_visible()
            page.wait_for_timeout(300)
            locked = page.locator('.pd-equipment-inspector').inner_text()
            close_id = page.get_by_role('button', name='Close', exact=True).get_attribute('id')
            cards.nth(2).hover()
            page.wait_for_timeout(400)
            assert page.locator('.pd-equipment-inspector').inner_text() == locked
            assert page.get_by_role('button', name='Close', exact=True).get_attribute('id') == close_id
        page.get_by_role('button', name='Saved Sets', exact=True).click()
        check('saved-sets', ['Close', 'Equip Saved', 'Restore Saved'])
        page.get_by_role('button', name='Close', exact=True).click()
        menu('Character & Stats')
        check('character', ['Return to Arena'])
        town()
        menu('Chronicle Records')
        check('records', ['Return to Town'])
        town()
        menu('Glossary')
        check('glossary', ['Return to Town'])
        town()
        for label in ['Inn', 'Marketplace', 'Transmutation', 'Well of Evil', 'Settings']:
            page.get_by_role('button', name=label, exact=True).first.click()
            for width, height in [(1280, 720), (960, 600), (1920, 1080)]:
                page.set_viewport_size({'width': width, 'height': height})
                check(label.replace(' ', '-'), ['Return to Town'])
            if label == 'Inn':
                page.get_by_role('button', name='Open Vault', exact=True).click()
                check('vault', ['Close', 'Deposit Selected', 'Withdraw Selected'])
                page.get_by_role('button', name='Close', exact=True).click()
            town()
        if args.seeded:
            menu('Return to Chronicle Slots')
            page.get_by_role('button', name='Open SSF', exact=True).click()
            page.locator('.mq-lab-grid').wait_for()
            for width, height in sizes[:4]:
                page.set_viewport_size({'width': width, 'height': height})
                check('labyrinth', ['Return to Town'], ['.mq-lab-grid', '.pd-expedition-brief'])
                assert page.locator('.mq-lab-member-card').count() == 5
            page.set_viewport_size({'width': 1280, 'height': 720})
            tank = page.locator('.mq-lab-member-card').first.locator('.mq-lab-tank-btn')
            tank.click()
            expect(tank).to_have_attribute('aria-pressed', 'true')
            assert tank.evaluate('e=>getComputedStyle(e).borderTopColor') == 'rgb(128, 228, 172)'
            page.get_by_role('button', name='Inventory', exact=True).first.click()
            check('lab-armory', ['Close'])
            page.get_by_role('button', name='Close', exact=True).click()
            page.locator('.mq-lab-grid').wait_for()
            before = page.locator('.mq-lab-tile').all_inner_texts().index('P')
            page.keyboard.press('ArrowRight')
            page.wait_for_function('before=>!document.querySelector(".mq-lab-grid")||[...document.querySelectorAll(".mq-lab-tile")].findIndex(e=>e.textContent.trim()==="P")!==before', arg=before)
        assert not external and not errors, (external, errors)
        print(json.dumps({'external_requests': external, 'page_errors': errors, 'passed': True}), flush=True)
        browser.close()


if __name__ == '__main__':
    main()
