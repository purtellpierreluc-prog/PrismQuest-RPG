"""Exercise formulas, fixed-geometry buttons and real Well combat in a disposable profile."""

import argparse
import copy
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reduced-motion', action='store_true')
    parser.add_argument('--encounters', type=int, default=2)
    args = parser.parse_args()
    if '.local-test' not in args.profile.resolve().parts:
        raise SystemExit('Only disposable profiles may be tested.')
    args.output.mkdir(parents=True, exist_ok=True)
    def slots():
        return json.loads((args.profile/'saves/chronicles.json').read_text(encoding='utf-8'))['slots']
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe', headless=True)
        page = browser.new_page(viewport={'width':1280,'height':720})
        if args.reduced_motion:
            page.emulate_media(reduced_motion='reduce')
        errors,external,reports = [],[],[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        def local(route):
            if urlsplit(route.request.url).hostname in {'127.0.0.1','localhost'}:
                route.continue_()
            else:
                external.append(route.request.url)
                route.abort()
        page.route('**/*',local)
        def cosmetic_controls():
            # Temporary DOM-only fixtures exercise browser semantics, never game actions.
            page.evaluate('''() => {
              const box=document.createElement('div');box.id='qa-controls';
              box.style='position:fixed;inset:150px auto auto 100px;z-index:30000;padding:30px;background:#111e23';
              box.innerHTML='<button class="q-btn mq-btn-secondary" id="qa-press" style="padding:15px"><span class="q-btn__content">QA press</span></button><button class="q-btn mq-btn-gold" disabled id="qa-disabled">Unavailable</button>';
              document.body.appendChild(box);window.qaClicks=0;
              box.querySelector('#qa-press').addEventListener('click',()=>window.qaClicks++);
            }''')
            target = page.locator('#qa-press')
            before = target.bounding_box()
            target.hover()
            page.mouse.down()
            assert target.bounding_box() == before
            assert target.evaluate('e=>getComputedStyle(e).transform') == 'none'
            assert target.evaluate('e=>e.classList.contains("pq-press")')
            page.mouse.up()
            assert page.evaluate('window.qaClicks') == 1
            target.focus()
            page.keyboard.press('Enter')
            page.keyboard.press('Space')
            assert page.evaluate('window.qaClicks') == 3
            disabled = page.locator('#qa-disabled')
            style = disabled.evaluate('e=>[getComputedStyle(e).transform,getComputedStyle(e).background,getComputedStyle(e).borderColor]')
            disabled.hover(force=True)
            assert disabled.evaluate('e=>[getComputedStyle(e).transform,getComputedStyle(e).background,getComputedStyle(e).borderColor]') == style
            page.wait_for_timeout(200)
            page.emulate_media(reduced_motion='reduce')
            target.click()
            assert not page.evaluate('window.PrismControls.inspect().animating')
            assert page.evaluate('window.qaClicks') == 4
            page.locator('#qa-controls').evaluate('e=>e.remove()')
            page.emulate_media(reduced_motion='reduce' if args.reduced_motion else 'no-preference')

        def cosmetic_reveal():
            page.evaluate('''() => {
              const result=document.createElement('section');result.id='qa-reveal';result.className='pw-answer';
              result.style='position:fixed;inset:150px auto auto 100px;width:400px;height:350px;z-index:30000';
              result.dataset.pwResult=JSON.stringify({key:'qa-only-'+Date.now(),outcome:'item',rarity:'Epic',reduced:false});
              result.innerHTML='<div class="pw-answer-body"><div class="mq-affix-line">QA only</div></div><div class="pw-answer-veil"><span class="pw-ripple"></span><span>QA only</span></div>';
              document.body.appendChild(result);
            }''')
            page.wait_for_timeout(700)
            before = page.evaluate('window.PrismWell.inspect()')
            assert before['active'] != args.reduced_motion
            page.locator('#qa-reveal').evaluate('e=>e.replaceWith(e.cloneNode(true))')
            page.wait_for_timeout(150)
            after = page.evaluate('window.PrismWell.inspect()')
            assert after['reveals'] == before['reveals']
            assert after['active'] != args.reduced_motion
            page.wait_for_timeout(2200)
            assert not page.evaluate('window.PrismWell.inspect().active')
            assert page.evaluate('window.PrismWell.inspect().animations') == 0
            page.locator('#qa-reveal').evaluate('e=>e.remove()')
        def button(name):
            return page.get_by_role('button',name=name,exact=True).first
        def check(name,selectors=()):
            page.mouse.move(3,3)
            page.wait_for_timeout(200)
            metrics = page.evaluate('''() => ({w:innerWidth,h:innerHeight,sw:document.scrollingElement.scrollWidth,sh:document.scrollingElement.scrollHeight})''')
            assert metrics['sw']<=metrics['w']+1 and metrics['sh']<=metrics['h']+1,(name,metrics)
            for selector in selectors:
                for box in page.locator(selector).evaluate_all('els=>els.map(e=>{let r=e.getBoundingClientRect();return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,h:r.height};})'):
                    assert box['h']>0 and box['bottom']<=metrics['h']+1 and box['right']<=metrics['w']+1,(name,selector,box,metrics)
            reports.append({'scene':name,**metrics})
            page.screenshot(path=str(args.output/f'{name}-{metrics["w"]}.png'))
        def sizes(name,selectors=()):
            for w,h in [(1280,720),(960,600),(800,500),(1920,1080)]:
                page.set_viewport_size({'width':w,'height':h})
                check(name,selectors)
            page.set_viewport_size({'width':1280,'height':720})
        page.goto(f'http://127.0.0.1:{args.port}',wait_until='networkidle')
        cosmetic_controls()
        cosmetic_reveal()
        if not page.locator('.pd-town-workspace').is_visible():
            button('Play').click()
            button('Open Core').click()
        page.locator('.pd-town-workspace').wait_for()
        original = copy.deepcopy(slots())
        button('Shape Your Build').click()
        page.locator('.pd-character-workspace').wait_for()
        dex = page.get_by_label('Dexterity formula and next point preview',exact=True)
        dex.hover()
        portal = page.locator('#pd-item-inspection')
        expect(portal).to_be_visible()
        assert 'does not shorten rounds or add attacks' in portal.inner_text()
        assert 'IF YOU ALLOCATE ONE POINT NOW' in portal.inner_text()
        assert slots()[0]['player'] == original[0]['player']
        page.screenshot(path=str(args.output/'dexterity-formula.png'))
        page.mouse.move(4,4)
        allocation = page.get_by_label('+1 Vitality',exact=True)
        box = allocation.bounding_box()
        allocation.hover()
        page.mouse.down()
        assert allocation.bounding_box() == box
        assert allocation.evaluate('e=>getComputedStyle(e).transform') == 'none'
        assert page.evaluate('window.PrismControls.inspect().pressed')
        page.mouse.up()
        remaining = original[0]['player']['unspent_stat_points']-1
        expect(page.locator('.pd-points-available')).to_have_text(f'{remaining} points to allocate')
        after = slots()
        assert after[0]['player']['base_vitality'] == original[0]['player']['base_vitality']+1
        assert after[0]['player']['unspent_stat_points'] == remaining
        assert after[1:] == original[1:]
        sizes('character',['.pd-character-build','.pd-character-readout'])
        button('Return to Arena').click()
        page.locator('.pd-arena-workspace').wait_for()
        button('Return to Town').click()
        page.locator('.pd-town-workspace').wait_for()
        button('Well of Evil').click()
        page.locator('.pw-workspace').wait_for()
        expect(button('Review the Bargain')).to_be_disabled()
        sizes('well-empty',['.pw-library','.pw-altar','.pw-answer','.pw-commit-zone'])
        disabled = button('Review the Bargain')
        before_style = disabled.evaluate('e=>({transform:getComputedStyle(e).transform,bg:getComputedStyle(e).background,border:getComputedStyle(e).borderColor})')
        disabled.hover(force=True)
        page.wait_for_timeout(200)
        assert disabled.evaluate('e=>({transform:getComputedStyle(e).transform,bg:getComputedStyle(e).background,border:getComputedStyle(e).borderColor})') == before_style
        shelf = page.locator('.pw-shelf')
        shelf.evaluate('e=>e.scrollTop=e.scrollHeight')
        page.wait_for_timeout(100)
        bottom = shelf.evaluate('e=>e.scrollTop')
        page.locator('[data-pw-item]').last.click()
        expect(page.locator('.pw-offering.selected')).to_have_count(1)
        assert abs(page.locator('.pw-shelf').evaluate('e=>e.scrollTop')-bottom)<2
        page.locator('.pw-offering.selected').focus()
        page.keyboard.press('ArrowUp')
        assert page.locator('[data-pw-item]').nth(page.locator('[data-pw-item]').count()-2).evaluate('e=>e===document.activeElement')
        page.keyboard.press('Enter')
        expect(page.locator('.pw-offering.selected')).to_have_count(1)
        page.locator('.pw-shelf').evaluate('e=>e.scrollTop=0')
        page.locator('[data-pw-item]').first.click()
        expect(page.locator('[data-pw-item]').first).to_have_attribute('aria-pressed','true')
        selected = page.locator('.pw-chosen').inner_text()
        before = copy.deepcopy(slots())
        button('Review the Bargain').click()
        assert slots()[0]['player'] == before[0]['player']
        assert selected.splitlines()[0] in page.locator('.pw-confirm-copy').inner_text()
        sizes('well-confirm',['.pw-commit-zone','.pw-confirm-actions'])
        outcomes = []
        for index in range(args.encounters):
            before = copy.deepcopy(slots())
            button('Cast Offering / 10g').click()
            page.locator('.pd-arena-workspace').wait_for(timeout=15000)
            page.locator('[data-pw-result]').wait_for(timeout=60000)
            signal = json.loads(page.locator('[data-pw-result]').get_attribute('data-pw-result'))
            outcomes.append(signal['outcome'])
            page.wait_for_timeout(200)
            presentation = page.evaluate('window.PrismWell.inspect()')
            if not args.reduced_motion:
                assert presentation['active'],presentation
            page.wait_for_timeout(2600)
            assert not page.evaluate('window.PrismWell.inspect().active')
            current = slots()
            assert current[0]['player']['gold'] == before[0]['player']['gold']-10
            found = signal['outcome'] == 'item'
            assert len(current[0]['player']['inventory']) == len(before[0]['player']['inventory'])-1+int(found)
            assert current[1:] == original[1:]
            if found:
                assert 'Already saved; no claim step' in page.locator('.pw-answer').inner_text()
                assert 'Base Profile' not in page.locator('.pw-answer').inner_text()
                assert current[0]['player']['inventory'][-1]['rarity']
                expect(button('Inspect Returned Item')).to_be_enabled()
            else:
                assert '50% return roll yielded no item' in page.locator('.pw-answer').inner_text()
            sizes(f'well-result-{index}',['.pw-answer','.pw-commit-zone'])
            count = page.evaluate('window.PrismWell.inspect().reveals')
            button('Return to Town').click()
            button('Well of Evil').click()
            page.wait_for_timeout(200)
            assert page.evaluate('window.PrismWell.inspect().reveals') == count
            if index+1 < args.encounters:
                page.locator('[data-pw-item]').first.click()
                button('Review the Bargain').click()
        assert not errors and not external, (errors,external)
        report = {'outcomes':outcomes,'viewports':reports,'errors':errors,'external':external,'controls':page.evaluate('window.PrismControls.inspect()'),'reveal':page.evaluate('window.PrismWell.inspect()')}
        (args.output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report))
        browser.close()


if __name__ == '__main__':
    main()
