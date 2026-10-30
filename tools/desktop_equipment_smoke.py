"""Exercise chronicle selection, item ownership and refresh-safe combat inspection."""

import argparse
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def owned_items(profile):
    document = json.loads((profile / 'saves/chronicles.json').read_text(encoding='utf-8'))
    slot = document['slots'][0]
    player = slot['player']
    items = list(player['inventory']) + list(player['equipped'].values()) + list(slot['vault_items'])
    for saved in slot['saved_item_sets'].values():
        items.extend(saved.values())
    return Counter(json.dumps(item, sort_keys=True) for item in items if item)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    profile = args.profile.resolve()
    if not profile.is_relative_to(ROOT / '.local-test'):
        raise SystemExit('Use a disposable .local-test profile only.')
    args.output.mkdir(parents=True, exist_ok=True)
    initial = owned_items(profile)
    errors, external = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe', headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 720})
        page.on('pageerror', lambda error: errors.append(str(error)))

        def local(route):
            if urlsplit(route.request.url).hostname in {'localhost', '127.0.0.1'}:
                route.continue_()
            else:
                external.append(route.request.url)
                route.abort()

        def fit(name, sizes=((1280, 720), (960, 600), (1920, 1080), (800, 500))):
            for w, h in sizes:
                page.set_viewport_size({'width': w, 'height': h})
                page.wait_for_timeout(200)
                assert page.evaluate('document.scrollingElement.scrollHeight<=innerHeight && document.scrollingElement.scrollWidth<=innerWidth')
                if page.locator('.mq-inventory-workspace').count():
                    header = page.locator('.mq-inv-hero-card').bounding_box()
                    panes = page.locator('.mq-inventory-panes').bounding_box()
                    actions = page.locator('.mq-inv-action-panel').bounding_box()
                    assert header['y'] >= 0 and header['height'] > 60, (name, w, header)
                    assert panes['y'] + panes['height'] <= actions['y'] + 1, (name, w, panes, actions)
                    assert actions['y'] + actions['height'] <= h + 1
                page.screenshot(path=str(args.output / f'{name}-{w}.png'))
            page.set_viewport_size({'width': 1280, 'height': 720})

        page.route('**/*', local)
        page.goto(f'http://127.0.0.1:{args.port}', wait_until='networkidle')
        page.get_by_role('button', name='Play', exact=True).click()
        page.locator('.pd-save-card').first.wait_for()
        expect(page.locator('.pd-save-card')).to_have_count(3)
        fit('chronicles')
        for mode in ('Core', 'SSF', 'HC'):
            expect(page.get_by_role('button', name=f'Open {mode}', exact=True)).to_be_in_viewport()
        page.get_by_role('button', name='Open Core', exact=True).click()
        page.get_by_role('button', name='Inventory', exact=True).first.click()
        cards = page.locator('.mq-manifest-entry-card')
        expect(cards).to_have_count(30)
        page.get_by_role('button', name='Saved Sets', exact=True).click()
        page.locator('.pd-collection-empty').wait_for()
        assert page.locator('.pd-collection-empty').bounding_box()['height'] > 100
        fit('protected-empty')
        page.get_by_role('button', name='Inventory', exact=True).last.click()
        cards.nth(2).click()
        page.wait_for_timeout(250)
        selected = page.locator('.pd-equipment-inspector').inner_text()
        cards.nth(3).hover()
        page.wait_for_timeout(250)
        assert page.locator('.pd-equipment-inspector').inner_text() == selected
        cards.nth(10).scroll_into_view_if_needed()
        scroll_before = page.locator('#mq-pack-manifest-scroll').evaluate('e=>e.scrollTop')
        cards.nth(10).click()
        page.wait_for_timeout(400)
        scroll_after = page.locator('#mq-pack-manifest-scroll').evaluate('e=>e.scrollTop')
        assert scroll_before > 0 and abs(scroll_after-scroll_before) < 5
        fit('workbench')
        page.get_by_role('button', name='Save Selected', exact=True).click()
        expect(cards).to_have_count(29)
        page.get_by_role('button', name='Saved Sets', exact=True).click()
        expect(cards).to_have_count(1)
        expect(page.get_by_role('button', name='Equip Saved', exact=True)).to_be_enabled()
        assert page.locator('.mq-inv-detail-panel').first.inner_text().lower().startswith('protected find')
        assert page.locator('#mq-pack-manifest-scroll').bounding_box()['height'] > 100
        fit('protected-item')
        page.get_by_role('button', name='Restore Saved', exact=True).click()
        expect(cards).to_have_count(30)
        page.get_by_role('button', name='Save Selected', exact=True).click()
        page.get_by_role('button', name='Saved Sets', exact=True).click()
        page.get_by_role('button', name='Equip Saved', exact=True).click()
        page.wait_for_timeout(800)
        assert owned_items(profile) == initial, 'Save/restore/equip must not duplicate or lose items.'
        page.get_by_role('button', name='Close', exact=True).click()
        page.get_by_role('button', name='Arena', exact=True).first.click()
        page.locator('.pd-combat-stats').wait_for()
        assert len(page.locator('.pd-combat-stats dd').all_text_contents()) == 6
        weapon = page.get_by_role('button', name='Inspect equipped Weapon', exact=True)
        weapon.hover()
        portal = page.locator('#pd-item-inspection')
        expect(portal).to_be_visible()
        text = portal.inner_text()
        page.mouse.move(650, 100)
        fit('arena-stats')
        page.get_by_role('button', name='Fight', exact=True).click()
        expect(page.get_by_role('button', name='Fight', exact=True)).to_be_disabled()
        weapon.hover()
        expect(portal).to_be_visible()
        page.evaluate('window.pdInspectionNode = document.querySelector("#pd-item-inspection")')
        page.wait_for_timeout(3600)
        assert portal.inner_text() == text
        assert page.evaluate('window.pdInspectionNode===document.querySelector("#pd-item-inspection")')
        assert page.evaluate('!document.querySelector("#pd-item-inspection").hidden')
        assert page.locator('.pd-battle-theatre.is-fighting').count() == 1
        page.screenshot(path=str(args.output / 'combat-inspection.png'))
        page.keyboard.press('Escape')
        expect(portal).to_be_hidden()
        weapon.focus()
        expect(portal).to_be_visible()
        page.keyboard.press('Escape')
        report = {'passed': True, 'ownership_preserved': True, 'combat_portal_stable': True, 'page_errors': errors, 'external_requests': external}
        (args.output / 'equipment-smoke.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        assert not errors and not external, report
        print(json.dumps(report, indent=2))
        browser.close()


if __name__ == '__main__':
    main()
