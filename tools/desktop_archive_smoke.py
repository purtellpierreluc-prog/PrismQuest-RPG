"""Verify the protected type/tier archive and independent item color channels."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from desktop_equipment_smoke import owned_items
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    profile = args.profile.resolve()
    if not profile.is_relative_to(ROOT / '.local-test'):
        raise SystemExit('Use a disposable visual-cues profile only.')
    initial = owned_items(profile)
    args.output.mkdir(parents=True, exist_ok=True)
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

        def fit(name):
            for w, h in [(1280, 720), (960, 600), (1920, 1080), (800, 500)]:
                page.set_viewport_size({'width': w, 'height': h})
                page.wait_for_timeout(200)
                assert page.evaluate('document.scrollingElement.scrollHeight<=innerHeight && document.scrollingElement.scrollWidth<=innerWidth')
                panes = page.locator('.mq-inventory-panes').bounding_box()
                actions = page.locator('.mq-inv-action-panel').bounding_box()
                assert panes['y'] + panes['height'] <= actions['y'] + 1
                assert actions['y'] + actions['height'] <= h + 1
                page.screenshot(path=str(args.output / f'{name}-{w}.png'))
            page.set_viewport_size({'width': 1280, 'height': 720})

        page.route('**/*', local)
        page.goto(f'http://127.0.0.1:{args.port}', wait_until='networkidle')
        if page.get_by_role('button', name='Play', exact=True).count():
            page.get_by_role('button', name='Play', exact=True).click()
            page.get_by_role('button', name='Open Core', exact=True).click()
            page.get_by_role('button', name='Inventory', exact=True).first.click()
        else:
            page.locator('.mq-inv-hero-card').get_by_role('button', name='Inventory', exact=True).click()
        cards = page.locator('.mq-manifest-entry-card')
        expect(cards).to_have_count(27)
        colors = page.locator('[data-item-rarity="Epic"]').evaluate_all('els=>els.map(e=>({type:e.dataset.itemType,border:getComputedStyle(e).borderLeftColor,background:getComputedStyle(e).backgroundImage}))')
        assert len({row['border'] for row in colors}) == 9
        assert len({row['background'] for row in colors}) <= 2, 'Selection may intensify the wash, not change its rarity.'
        dagger = page.locator('[data-item-type="dagger"][data-item-rarity="Epic"]')
        dagger.click()
        page.wait_for_timeout(250)
        frames = page.locator('.mq-manifest-entry-card[data-item-type="dagger"]')
        border_colors = frames.evaluate_all('els=>els.map(e=>getComputedStyle(e).borderLeftColor)')
        assert len(set(border_colors)) == 1, 'Rarity and selection must not change the type frame.'
        fit('item-language')
        page.locator('.pd-item-key summary').click()
        expect(page.locator('.pd-item-key-popover')).to_be_visible()
        expect(page.locator('.pd-item-key-types span')).to_have_count(9)
        page.screenshot(path=str(args.output / 'visual-key.png'))
        page.locator('.pd-item-key summary').click()
        page.get_by_role('button', name='Saved Sets', exact=True).click()
        expect(page.locator('.pd-saved-family')).to_have_count(9)
        expect(page.locator('.pd-saved-mark')).to_have_count(90)
        expect(page.locator('.pd-saved-item')).to_have_count(9)
        assert not page.locator('.pd-equipment-inspector').count()
        fit('saved-archive')
        mark = page.locator('[data-saved-category="dagger"][data-saved-tier="5"]')
        mark.locator('.pd-saved-item').click()
        page.keyboard.down('Control')
        mark.locator('.pd-saved-item').hover()
        expect(page.locator('#pd-item-inspection')).to_be_visible()
        assert 'Epic' in page.locator('#pd-item-inspection').inner_text()
        page.keyboard.up('Control')
        page.mouse.move(600, 100)
        toggle = page.get_by_role('button', name='Toggle Dagger saved marks', exact=True)
        toggle.click()
        expect(toggle).to_have_attribute('aria-expanded', 'false')
        toggle.click()
        expect(toggle).to_have_attribute('aria-expanded', 'true')
        expect(mark.locator('.pd-saved-item')).to_have_attribute('aria-selected', 'true')
        page.get_by_text('All rarities', exact=True).click()
        page.get_by_role('option', name='Rare', exact=True).click()
        expect(mark.locator('.pd-saved-empty-mark.filtered')).to_be_visible()
        assert 'Filtered item' in mark.inner_text() and 'Empty mark' not in mark.inner_text()
        page.get_by_role('button', name='Reset Filters', exact=True).click()
        expect(page.locator('.pd-saved-item')).to_have_count(9)
        expect(page.get_by_text('All rarities', exact=True)).to_be_visible()
        axe = page.locator('[data-saved-category="axe"][data-saved-tier="1"] .pd-saved-item')
        previous_action = page.get_by_role('button', name='Restore Saved', exact=True).get_attribute('id')
        axe.click()
        expect(axe).to_have_attribute('aria-selected', 'true')
        expect(page.get_by_role('button', name='Restore Saved', exact=True)).to_have_attribute('id', previous_action)
        page.get_by_role('button', name='Restore Saved', exact=True).click()
        expect(cards).to_have_count(28)
        previous_action = page.get_by_role('button', name='Save Selected', exact=True).get_attribute('id')
        page.locator('.mq-manifest-entry-card[data-item-type="axe"][data-item-tier="1"]').click()
        expect(page.get_by_role('button', name='Save Selected', exact=True)).to_have_attribute('id', previous_action)
        page.get_by_role('button', name='Save Selected', exact=True).click()
        expect(cards).to_have_count(27)
        page.get_by_role('button', name='Saved Sets', exact=True).click()
        expect(page.locator('.pd-saved-item')).to_have_count(9)
        page.wait_for_timeout(800)
        assert owned_items(profile) == initial
        page.reload(wait_until='networkidle')
        expect(page.locator('.pd-saved-family')).to_have_count(9)
        expect(page.locator('.pd-saved-item')).to_have_count(9)
        page.get_by_role('button', name='Close', exact=True).click()
        page.get_by_role('button', name='Arena', exact=True).first.click()
        page.get_by_role('button', name='Fight', exact=True).click()
        page.locator('.pd-battle-theatre.is-fighting').wait_for()
        page.wait_for_function('document.querySelector(".pd-enemy")?.dataset.defense !== "none"')
        cue = page.locator('.pd-enemy').get_attribute('data-defense')
        assert cue in {'species', 'armor', 'ward', 'both'}
        assert page.locator('.pd-enemy').evaluate('e=>getComputedStyle(e).getPropertyValue("--mq-monster-rgb").trim()')
        if cue == 'species':
            aura = page.locator('.pd-enemy .pd-art-plate').evaluate('e=>getComputedStyle(e,"::before").backgroundImage')
            assert '145, 165, 158' in aura, 'Ordinary enemies must not borrow a misleading blue species aura.'
        page.screenshot(path=str(args.output / 'monster-aura.png'))
        report = {'passed': True, 'ownership_preserved': True, 'groups': 9, 'marks': 90, 'type_frames': 9, 'encounter_defense_cue': cue, 'page_errors': errors, 'external_requests': external}
        assert not errors and not external, report
        (args.output / 'archive-smoke.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report, indent=2))
        browser.close()


if __name__ == '__main__':
    main()
