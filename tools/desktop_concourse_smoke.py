"""Exercise the Concourse on a disposable seeded desktop profile."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe', headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 720})
        errors, external, reports = [], [], []
        def route(request):
            if urlsplit(request.request.url).hostname in {'127.0.0.1', 'localhost'}:
                request.continue_()
            else:
                external.append(request.request.url)
                request.abort()
        page.route('**/*', route)
        page.on('pageerror', lambda error: errors.append(str(error)))
        def button(name):
            return page.get_by_role('button', name=name, exact=True).first
        def check(name):
            page.wait_for_timeout(350)
            metrics = page.evaluate('''() => {
                const root=document.scrollingElement, content=document.querySelector('.pn-workspace');
                const box=content.getBoundingClientRect();
                return {w:innerWidth,h:innerHeight,sw:root.scrollWidth,sh:root.scrollHeight,
                        panel:{x:box.x,y:box.y,right:box.right,bottom:box.bottom},
                        body:getComputedStyle(document.querySelector('.pn-body')||content).display};
            }''')
            assert metrics['sw'] <= metrics['w']+1 and metrics['sh'] <= metrics['h']+1, (name, metrics)
            assert metrics['panel']['bottom'] <= metrics['h']+1, (name, metrics)
            page.screenshot(path=str(args.output / f'{name}-{metrics["w"]}.png'))
            reports.append({'scene': name, **metrics})
        page.goto(f'http://127.0.0.1:{args.port}', wait_until='networkidle')
        button('Play').click()
        button('Open Core').click()
        page.wait_for_timeout(400)
        if button('Return to Town').is_visible():
            button('Return to Town').click()
        button('Concourse').click()
        expect(button('Enter Test Realm')).to_be_visible()
        for w, h in [(1280,720), (960,600), (1920,1080)]:
            page.set_viewport_size({'width':w,'height':h})
            check('entry')
        page.set_viewport_size({'width':1280,'height':720})
        button('Enter Test Realm').click()
        expect(button('Prepare Test Character')).to_be_visible(timeout=30000)
        button('Prepare Test Character').click()
        expect(page.get_by_text('2,000 GOLD', exact=True)).to_be_visible()
        check('expedition')
        for title in ['Armory & Courier', 'Bazaar', 'Guild Hall', 'Realm Ladder']:
            button(title).click()
            check(title.lower().replace(' ', '-').replace('&', 'and'))
        button('Armory & Courier').click()
        page.keyboard.down('Control')
        page.locator('.pn-item .pd-inspect-trigger').first.hover()
        page.wait_for_timeout(500)
        page.screenshot(path=str(args.output / 'item-inspection.png'))
        page.keyboard.up('Control')
        button('Deposit').first.click()
        expect(page.get_by_text('Item deposited.', exact=True)).to_be_visible()
        page.get_by_role('button', name='Vault', exact=True).click()
        expect(button('Withdraw')).to_be_visible()
        button('List').click()
        expect(page.get_by_text('Offer to the Bazaar', exact=True)).to_be_visible()
        page.get_by_label('Gold price', exact=True).fill('123')
        button('Create Listing').click()
        button('Bazaar').click()
        button('My Listings').click()
        expect(button('Change Price')).to_be_visible()
        button('Change Price').click()
        page.get_by_label('Gold price', exact=True).fill('234')
        button('Save Price').click()
        expect(page.get_by_text('234 gold / Prism Wanderer', exact=True)).to_be_visible()
        button('Cancel Listing').click()
        expect(page.get_by_text('Listing returned to your realm vault.', exact=True)).to_be_visible()
        button('Guild Hall').click()
        page.get_by_label('Guild name', exact=True).fill('Prism Keepers')
        button('Found Guild').click()
        expect(page.get_by_text('Guild created.', exact=True)).to_be_visible()
        page.get_by_label('Message', exact=True).fill('The light is with us.')
        button('Send Message').click()
        expect(page.get_by_text('The light is with us.', exact=True)).to_be_visible()
        button('Expedition').click()
        button('Open Expedition').click()
        expect(page.get_by_text('Party opened. Share the invitation code with up to four friends.', exact=True)).to_be_visible()
        button('Ready Up').click()
        expect(button('Not Ready')).to_be_visible()
        button('Enter the Labyrinth').click()
        expect(page.locator('.pn-tile')).to_have_count(49)
        for w, h in [(1280,720), (960,600), (1920,1080)]:
            page.set_viewport_size({'width':w,'height':h})
            check('shared-labyrinth')
        page.set_viewport_size({'width':1280,'height':720})
        button('North').click()
        expect(page.get_by_text('Party updated.', exact=True)).to_be_visible()
        page.wait_for_timeout(3400)
        check('shared-labyrinth-moved')
        button('Return to Solo').click()
        expect(page.locator('.pd-town-workspace')).to_be_visible()
        page.wait_for_timeout(3500)
        assert not errors, errors
        assert not external, external
        (args.output / 'report.json').write_text(json.dumps({'errors':errors,'external':external,'scenes':reports}, indent=2), encoding='utf-8')
        browser.close()
        print(json.dumps({'passed':True,'scenes':len(reports),'external_requests':len(external)}))


if __name__ == '__main__':
    main()
