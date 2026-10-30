"""Real crafting, conservation, accessibility and bounded-workspace acceptance."""

import argparse
import copy
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright


def canonical(item):
    return json.dumps(item, sort_keys=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if '.local-test' not in args.profile.resolve().parts:
        raise SystemExit('Only disposable .local-test profiles may be used.')
    args.output.mkdir(parents=True, exist_ok=True)
    def slot():
        return json.loads((args.profile / 'saves/chronicles.json').read_text(encoding='utf-8'))['slots'][0]
    original = copy.deepcopy(slot())
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe', headless=True)
        page = browser.new_page(viewport={'width':1280,'height':720})
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
            page.mouse.move(5,5)
            page.wait_for_timeout(180)
            metrics = page.evaluate('''() => ({w:innerWidth,h:innerHeight,sw:document.scrollingElement.scrollWidth,sh:document.scrollingElement.scrollHeight,
              panels:[...document.querySelectorAll('.pc-workspace,.pc-library,.pc-bench,.pc-outcome,.pc-commit-zone,.pc-result-actions,.pc-confirm-actions')].map(e=>{
              const r=e.getBoundingClientRect(); return {c:e.className,x:r.x,y:r.y,right:r.right,bottom:r.bottom,w:r.width,h:r.height};})})''')
            assert metrics['sw'] <= metrics['w']+1 and metrics['sh'] <= metrics['h']+1, metrics
            for panel in metrics['panels']:
                assert panel['h'] > 0 and panel['bottom'] <= metrics['h']+1 and panel['right'] <= metrics['w']+1, (name, panel, metrics)
            reports.append({'scene':name,**metrics})
            page.screenshot(path=str(args.output / f'{name}-{metrics["w"]}.png'))
        def choose_pair():
            first = page.locator('.pc-offering:not([disabled])').first
            one = int(first.get_attribute('data-pc-index'))
            first.click()
            expect(page.locator('.pc-offering.chosen')).to_have_count(1)
            second = page.locator('.pc-offering:not([disabled])').first
            two = int(second.get_attribute('data-pc-index'))
            second.click()
            expect(button('Review Transmutation')).to_be_enabled()
            return one, two
        page.goto(f'http://127.0.0.1:{args.port}', wait_until='networkidle')
        button('Play').click()
        button('Open Core').click()
        page.locator('.pd-town-workspace').wait_for()
        button('Transmutation').click()
        page.locator('.pc-workspace').wait_for()
        assert not page.locator('.pc-offering.chosen').count()
        assert not page.locator('.pc-result').count()
        for w,h in [(1280,720),(960,600),(1920,1080),(800,500),(2560,1080)]:
            page.set_viewport_size({'width':w,'height':h})
            check('empty')
        page.set_viewport_size({'width':1280,'height':720})
        search = page.get_by_label('Find an offering', exact=True)
        search.fill('axe')
        expect(page.locator('.pc-offering')).to_have_count(2)
        focus_id = search.get_attribute('id')
        page.wait_for_timeout(2200)
        assert search.get_attribute('id') == focus_id
        assert search.evaluate('e=>e===document.activeElement')
        search.fill('')
        expect(page.locator('.pc-offering')).to_have_count(18)
        first_row = page.locator('.pc-offering:not([disabled])').first
        first_row.focus()
        first_row.press('ArrowDown')
        assert page.locator('.pc-offering:not([disabled])').nth(1).evaluate('e=>e===document.activeElement')
        page.locator('.pc-library-scroll').evaluate('e=>e.scrollTop=170')
        row = page.locator('.pc-offering:not([disabled])').nth(3)
        row.scroll_into_view_if_needed()
        scroll = page.locator('.pc-library-scroll').evaluate('e=>e.scrollTop')
        row.click()
        expect(page.locator('.pc-offering.chosen')).to_have_count(1)
        assert abs(page.locator('.pc-library-scroll').evaluate('e=>e.scrollTop') - scroll) < 3
        button('Remove form').click()
        expect(page.locator('.pc-offering.chosen')).to_have_count(0)
        one,two = choose_pair()
        before = slot()
        offered = [before['player']['inventory'][i] for i in (one,two)]
        fee = 2 + sum(len(item['affix_stats']) for item in offered)
        check('ready')
        button('Review Transmutation').click()
        expect(page.get_by_text('These two offerings will be consumed.', exact=True)).to_be_visible()
        assert slot()['player'] == before['player']
        check('confirmation')
        page.get_by_role('button',name=f'Confirm Transmutation / {fee}g',exact=True).click()
        page.locator('.pc-result').wait_for()
        page.wait_for_function('window.PrismCrucible.inspect().active')
        result_id = page.locator('.pc-result').get_attribute('id')
        expect(page.locator('.pc-new-forged')).to_have_count(1)
        check('reveal')
        page.wait_for_function('!window.PrismCrucible.inspect().active', timeout=8000)
        assert page.locator('.pc-result').get_attribute('id') == result_id
        assert not page.locator('.pc-new-forged').count()
        assert page.locator('.pc-result-name').evaluate('e=>e===document.activeElement')
        after = slot()
        assert after['player']['gold'] == before['player']['gold'] - fee
        assert len(after['player']['inventory']) == len(before['player']['inventory']) - 1
        expected = Counter(canonical(item) for item in before['player']['inventory'])
        expected.subtract(canonical(item) for item in offered)
        expected.update([canonical(after['player']['inventory'][-1])])
        actual = Counter(canonical(item) for item in after['player']['inventory'])
        assert +expected == actual, {'indices':[one,two], 'offered':offered, 'missing':list((+expected-actual).elements()),'unexpected':list((actual-+expected).elements())}
        for key in ('saved_item_sets','vault_items','labyrinth_roster_companions'):
            assert original.get(key) == after.get(key), key
        assert original['player']['equipped'] == after['player']['equipped']
        for w,h in [(1280,720),(960,600),(800,500),(1920,1080)]:
            page.set_viewport_size({'width':w,'height':h})
            check('result')
        page.set_viewport_size({'width':1280,'height':720})
        assert page.evaluate('window.PrismCrucible.inspect().reveals') == 1
        button('Return to Town').click()
        button('Transmutation').click()
        page.locator('.pc-result').wait_for()
        assert page.evaluate('window.PrismCrucible.inspect().reveals') == 1
        assert not page.evaluate('window.PrismCrucible.inspect().active')
        button('Use as Next Form').click()
        expect(page.locator('.pc-offering.chosen')).to_have_count(1)
        second = page.locator('.pc-offering:not([disabled])').first
        second.click()
        button('Review Transmutation').click()
        page.emulate_media(reduced_motion='reduce')
        page.get_by_role('button',name='Confirm Transmutation /',exact=False).click()
        page.wait_for_function('window.PrismCrucible.inspect().reveals===2')
        assert not page.evaluate('window.PrismCrucible.inspect().active')
        assert not page.locator('.pc-reveal-veil').count()
        assert len(slot()['player']['inventory']) == len(original['player']['inventory']) - 2
        check('reduced-motion-result')
        assert not errors, errors
        assert not external, external
        report = {'passed':True,'errors':errors,'external':external,'rituals':2,'conservation':True,'scenes':reports}
        (args.output / 'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({'passed':True,'rituals':2,'scenes':len(reports),'external':external}))
        browser.close()


if __name__ == '__main__':
    main()
